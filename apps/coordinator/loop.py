import logging
import os
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from coordinator.sink import RunEventSink
from domain.states import (
    AttemptState,
    EventSeverity,
    Recoverability,
    RunControlState,
)
from domain.transitions import next_attempt_state, next_run_state
from engine.base import (
    Engine,
    EngineError,
    EngineOutcome,
    EngineResult,
    EngineRunRequest,
)
from persistence import leases
from persistence.attempts import create_attempt
from persistence.events import append_event
from persistence.models import ExecutionAttempt, Run

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
) -> None:
    attempt.state = next_attempt_state(attempt.state, AttemptState.EXITED)
    attempt.ended_at = moment
    attempt.terminal_reason = terminal_reason
    run.active_attempt_id = None
    run.control_state = next_run_state(run.control_state, RunControlState.FAILED)
    run.failure_class = failure_class
    run.failure_code = failure_code
    run.failure_summary = failure_summary
    run.recoverability = Recoverability.UNKNOWN
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


async def drive_run(
    session: AsyncSession,
    run: Run,
    engine_factory: EngineFactory,
    *,
    holder_id: str,
    now: datetime | None = None,
) -> None:
    moment = _naive_now(now)
    lease = await leases.acquire(
        session, project_id=run.project_id, holder_id=holder_id, run_id=run.id
    )
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
        request = EngineRunRequest(
            project_id=run.project_id, run_id=run.id, attempt_id=attempt.id
        )
        try:
            engine = await engine_factory(session, run)
            result = await engine.run(request, RunEventSink(session, run, attempt.id))
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
            if result.outcome is EngineOutcome.COMPLETED_VERIFIED:
                await _finish_completed(session, run, attempt, moment)
            else:
                failure_code, failure_summary = _failure_details(result)
                await _finish_failed(
                    session,
                    run,
                    attempt,
                    moment,
                    terminal_reason="ENGINE_OUTCOME",
                    failure_class="ENGINE_FAILURE",
                    failure_code=failure_code,
                    failure_summary=failure_summary,
                )
        run.version += 1
        run.updated_at = moment
        await session.flush()
    finally:
        await leases.release(
            session,
            project_id=run.project_id,
            holder_id=holder_id,
            lease_epoch=lease.lease_epoch,
        )
    await session.commit()


async def process_queued_runs(
    session: AsyncSession,
    *,
    holder_id: str,
    engine_factory: EngineFactory,
    now: datetime | None = None,
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
        try:
            await drive_run(session, run, engine_factory, holder_id=holder_id, now=now)
            processed += 1
        except leases.LeaseConflictError:
            continue
    return processed
