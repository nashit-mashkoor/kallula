import asyncio
import logging
import os
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from coordinator.active import ActiveRun, ActiveRuns
from coordinator.sink import RunEventSink
from domain.interactions import TITLES, allowed_responses, interaction_kind
from domain.states import (
    AttemptState,
    EventSeverity,
    InteractionResponseType,
    InteractionState,
    Recoverability,
    RunControlState,
)
from domain.transitions import next_attempt_state, next_run_state
from engine.base import (
    Engine,
    EngineError,
    EngineInteraction,
    EngineInteractionResponse,
    EngineOutcome,
    EngineResult,
    EngineRunRequest,
)
from persistence import interactions as interactions_repo
from persistence import leases
from persistence.attempts import create_attempt
from persistence.events import append_event
from persistence.models import ExecutionAttempt, PendingInteraction, Run

logger = logging.getLogger("coordinator")

POLL_INTERVAL_SECONDS = 1.0

EngineFactory = Callable[[AsyncSession, Run], Awaitable[Engine]]


def default_holder_id() -> str:
    return f"coordinator-{os.getpid()}"


def _naive_now(moment: datetime | None = None) -> datetime:
    return (moment or datetime.now(UTC)).replace(tzinfo=None)


def _failure_details(result: EngineResult) -> tuple[str, str]:
    if result.outcome is EngineOutcome.TERMINAL_UNVERIFIED_OR_INCOMPLETE:
        return (
            "ENGINE_UNVERIFIED",
            result.failure_summary or "Engine finished without verified completion.",
        )
    return "ENGINE_FAILED", result.failure_summary or "Run failed."


async def _watch_stop(signal: asyncio.Event, engine: Engine) -> None:
    await signal.wait()
    engine.request_safe_stop()


def engine_interaction_response(
    response, interaction: PendingInteraction
) -> EngineInteractionResponse:
    """The accepted response as the engine consumes it, keyed natively."""
    accept = response.response_type is InteractionResponseType.CONFIRM
    if response.response_type is InteractionResponseType.DELEGATE_REMAINING:
        answer = "auto"
    elif response.response_type is InteractionResponseType.USE_RECOMMENDATION:
        answer = response.answer_text or interaction.recommendation or ""
    else:
        answer = response.answer_text or ""
    return EngineInteractionResponse(
        interaction_id=interaction.engine_interaction_token,
        kind=interaction.kind.value,
        accept=accept,
        answer="" if accept else answer,
    )


async def _finish_waiting(
    session: AsyncSession,
    run: Run,
    attempt: ExecutionAttempt | None,
    moment: datetime,
    interaction: EngineInteraction,
) -> None:
    """Suspend the Run on a durable pending interaction (KSA-REQ-050)."""
    if attempt is not None:
        attempt.state = next_attempt_state(attempt.state, AttemptState.EXITED)
        attempt.ended_at = moment
        attempt.terminal_reason = "WAITING_FOR_HUMAN"
    run.active_attempt_id = None
    if run.control_state is not RunControlState.WAITING_FOR_HUMAN:
        run.control_state = next_run_state(
            run.control_state, RunControlState.WAITING_FOR_HUMAN
        )
    kind = interaction_kind(interaction.kind)
    pending = await interactions_repo.open_for_run(session, run.id)
    if (
        pending is not None
        and pending.engine_interaction_token == interaction.native_id
    ):
        # The same native question survives a stop/resume cycle: reuse it.
        pending.attempt_id = attempt.id if attempt is not None else pending.attempt_id
        pending.version += 1
        opened = False
    else:
        if pending is not None:
            pending.status = InteractionState.SUPERSEDED
            pending.resolved_at = moment
            pending.version += 1
        pending = PendingInteraction(
            run_id=run.id,
            attempt_id=attempt.id if attempt is not None else None,
            kind=kind,
            status=InteractionState.OPEN,
            title=TITLES[kind],
            prompt=interaction.question,
            recommendation=interaction.recommendation,
            context_json={"accepted_turns": []},
            allowed_responses_json=allowed_responses(kind),
            engine_interaction_token=interaction.native_id,
        )
        session.add(pending)
        await session.flush()
        opened = True
    run.pending_interaction_id = pending.id
    if attempt is not None:
        await append_event(
            session,
            run,
            event_type="ATTEMPT_EXITED",
            category="ATTEMPT",
            summary="Attempt exited to wait for human input.",
            attempt_id=attempt.id,
        )
    await append_event(
        session,
        run,
        event_type="RUN_WAITING_FOR_HUMAN",
        category="RUN",
        summary="Run is waiting for human input.",
        payload={"interaction_id": pending.id},
    )
    if opened:
        await append_event(
            session,
            run,
            event_type="INTERACTION_OPENED",
            category="INTERACTION",
            summary="Human interaction opened.",
            payload={
                "interaction_id": pending.id,
                "kind": pending.kind.value,
            },
        )


async def _finish_failed(
    session: AsyncSession,
    run: Run,
    attempt: ExecutionAttempt,
    moment: datetime,
    *,
    terminal_reason: str,
    failure_class: str,
    failure_code: str,
    failure_summary: str,
    recoverability: Recoverability = Recoverability.UNKNOWN,
) -> None:
    attempt.state = next_attempt_state(attempt.state, AttemptState.EXITED)
    attempt.ended_at = moment
    attempt.terminal_reason = terminal_reason
    run.active_attempt_id = None
    run.control_state = next_run_state(run.control_state, RunControlState.FAILED)
    run.failure_class = failure_class
    run.failure_code = failure_code
    run.failure_summary = failure_summary
    run.recoverability = recoverability
    await append_event(
        session,
        run,
        event_type="ATTEMPT_EXITED",
        category="ATTEMPT",
        summary="Attempt exited with an engine failure.",
        attempt_id=attempt.id,
    )
    await append_event(
        session,
        run,
        event_type="RUN_FAILED",
        category="RUN",
        severity=EventSeverity.ERROR,
        summary=failure_summary,
        payload={"code": failure_code},
    )


async def _finish_completed(
    session: AsyncSession,
    run: Run,
    attempt: ExecutionAttempt,
    moment: datetime,
) -> None:
    attempt.state = next_attempt_state(attempt.state, AttemptState.EXITED)
    attempt.ended_at = moment
    attempt.terminal_reason = "ENGINE_OUTCOME"
    run.active_attempt_id = None
    run.control_state = next_run_state(run.control_state, RunControlState.COMPLETED)
    run.completed_at = moment
    await append_event(
        session,
        run,
        event_type="ATTEMPT_EXITED",
        category="ATTEMPT",
        summary="Attempt exited with an engine outcome.",
        attempt_id=attempt.id,
    )
    await append_event(
        session,
        run,
        event_type="RUN_COMPLETED",
        category="RUN",
        summary="Run completed.",
    )


async def _finish_stopped(
    session: AsyncSession,
    run: Run,
    attempt: ExecutionAttempt,
    moment: datetime,
) -> None:
    attempt.state = next_attempt_state(attempt.state, AttemptState.EXITED)
    attempt.ended_at = moment
    attempt.terminal_reason = "SAFE_STOP"
    run.active_attempt_id = None
    run.control_state = next_run_state(run.control_state, RunControlState.STOPPED)
    await append_event(
        session,
        run,
        event_type="ATTEMPT_EXITED",
        category="ATTEMPT",
        summary="Attempt exited at a safe boundary.",
        attempt_id=attempt.id,
    )
    await append_event(
        session,
        run,
        event_type="RUN_STOPPED",
        category="RUN",
        summary="Run stopped safely.",
    )


async def drive_run(
    session: AsyncSession,
    run: Run,
    engine_factory: EngineFactory,
    *,
    holder_id: str,
    now: datetime | None = None,
    active: ActiveRun | None = None,
) -> None:
    moment = _naive_now(now)
    stop_signal = active.signal if active is not None else None
    lease = await leases.acquire(
        session, project_id=run.project_id, holder_id=holder_id, run_id=run.id
    )
    if active is not None:
        active.project_id = run.project_id
        active.holder_id = holder_id
        active.lease_epoch = lease.lease_epoch
    try:
        run.control_state = next_run_state(run.control_state, RunControlState.STARTING)
        await append_event(
            session,
            run,
            event_type="RUN_STARTING",
            category="RUN",
            summary="Run is starting.",
        )
        attempt = await create_attempt(session, run)
        attempt.worker_runtime_ref = f"pid:{os.getpid()}"
        run.active_attempt_id = attempt.id
        run.started_at = run.started_at or moment
        run.control_state = next_run_state(run.control_state, RunControlState.RUNNING)
        run.version += 1
        run.updated_at = moment
        await append_event(
            session,
            run,
            event_type="ATTEMPT_ALLOCATED",
            category="ATTEMPT",
            summary=f"Attempt {attempt.ordinal} allocated.",
            attempt_id=attempt.id,
        )
        await session.flush()

        attempt.state = next_attempt_state(attempt.state, AttemptState.STARTING)
        await append_event(
            session,
            run,
            event_type="ATTEMPT_STARTED",
            category="ATTEMPT",
            summary="Attempt started.",
            attempt_id=attempt.id,
        )
        await append_event(
            session,
            run,
            event_type="RUN_STARTED",
            category="RUN",
            summary="Run started.",
            attempt_id=attempt.id,
        )
        await session.commit()
        accepted = await interactions_repo.latest_response_for_run(session, run.id)
        request = EngineRunRequest(
            project_id=run.project_id,
            run_id=run.id,
            attempt_id=attempt.id,
            response=engine_interaction_response(*accepted) if accepted else None,
        )
        try:
            engine = await engine_factory(session, run)
            watcher = (
                asyncio.create_task(_watch_stop(stop_signal, engine))
                if stop_signal is not None
                else None
            )
            try:
                result = await engine.run(
                    request, RunEventSink(session, run, attempt.id)
                )
            finally:
                if watcher is not None:
                    watcher.cancel()
        except EngineError as exc:
            await _finish_failed(
                session,
                run,
                attempt,
                moment,
                terminal_reason="ADAPTER_FAILURE",
                failure_class="ENGINE_ADAPTER",
                failure_code=exc.code,
                failure_summary=exc.detail,
            )
        else:
            if (
                result.outcome is EngineOutcome.WAITING_FOR_HUMAN
                and result.interaction is not None
            ):
                await _finish_waiting(session, run, attempt, moment, result.interaction)
            elif result.outcome is EngineOutcome.COMPLETED_VERIFIED:
                await _finish_completed(session, run, attempt, moment)
            elif result.outcome is EngineOutcome.STOPPED_SAFE:
                await _finish_stopped(session, run, attempt, moment)
            elif result.outcome is EngineOutcome.WAITING_FOR_HUMAN:
                await _finish_failed(
                    session,
                    run,
                    attempt,
                    moment,
                    terminal_reason="ENGINE_OUTCOME",
                    failure_class="ENGINE_FAILURE",
                    failure_code="ENGINE_INTERACTION_MISSING",
                    failure_summary=(
                        "The engine suspended without a pending interaction."
                    ),
                )
            else:
                failure_code, failure_summary = _failure_details(result)
                recoverability = (
                    Recoverability.RESUMABLE
                    if failure_code == "ENGINE_UNVERIFIED"
                    else Recoverability.UNKNOWN
                )
                await _finish_failed(
                    session,
                    run,
                    attempt,
                    moment,
                    terminal_reason="ENGINE_OUTCOME",
                    failure_class="ENGINE_FAILURE",
                    failure_code=failure_code,
                    failure_summary=failure_summary,
                    recoverability=recoverability,
                )
        run.version += 1
        run.updated_at = moment
        await session.flush()
        await session.commit()
    finally:
        try:
            await leases.release(
                session,
                project_id=run.project_id,
                holder_id=holder_id,
                lease_epoch=lease.lease_epoch,
            )
            await session.commit()
        except leases.LeaseConflictError:
            await session.rollback()


async def process_queued_runs(
    session: AsyncSession,
    *,
    holder_id: str,
    engine_factory: EngineFactory,
    now: datetime | None = None,
    active: ActiveRuns | None = None,
) -> int:
    runs = (
        (
            await session.execute(
                select(Run)
                .where(Run.control_state == RunControlState.QUEUED)
                .order_by(Run.ordinal)
            )
        )
        .scalars()
        .all()
    )
    processed = 0
    for run in runs:
        if active is not None and active.is_active(run.id):
            continue
        entry = active.register(run.id) if active is not None else None
        try:
            await drive_run(
                session,
                run,
                engine_factory,
                holder_id=holder_id,
                now=now,
                active=entry,
            )
            processed += 1
        except leases.LeaseConflictError:
            continue
        finally:
            if active is not None:
                active.unregister(run.id)
    return processed


async def settle_stop_requested_runs(
    session: AsyncSession,
    *,
    active: ActiveRuns | None = None,
    now: datetime | None = None,
) -> int:
    """Settle stop requests no worker can carry out: a Run with no active
    Attempt (for example one suspended on a pending interaction, KSA-REQ-050)
    stops where it is instead of staying in STOP_REQUESTED."""
    moment = _naive_now(now)
    runs = (
        (
            await session.execute(
                select(Run)
                .where(Run.control_state == RunControlState.STOP_REQUESTED)
                .order_by(Run.ordinal)
            )
        )
        .scalars()
        .all()
    )
    settled = 0
    for run in runs:
        if active is not None and active.is_active(run.id):
            continue
        if run.active_attempt_id is not None:
            continue
        run.control_state = next_run_state(run.control_state, RunControlState.STOPPED)
        run.version += 1
        run.updated_at = moment
        await append_event(
            session,
            run,
            event_type="RUN_STOPPED",
            category="RUN",
            summary="Run stopped safely; no worker was carrying out the request.",
        )
        settled += 1
    if settled:
        await session.commit()
    return settled
