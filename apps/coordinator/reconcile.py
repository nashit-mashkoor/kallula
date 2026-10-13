import logging
import os
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from coordinator.loop import EngineFactory, _finish_waiting
from domain.states import (
    AttemptState,
    EventSeverity,
    Recoverability,
    RunControlState,
)
from domain.transitions import can_transition_run, next_attempt_state, next_run_state
from engine.base import EngineError, EngineOutcome, EngineResult
from persistence import interactions as interactions_repo
from persistence import leases
from persistence.events import append_event
from persistence.models import ExecutionAttempt, Run

logger = logging.getLogger("coordinator")

ACTIVE_RUN_STATES = (
    RunControlState.STARTING,
    RunControlState.RUNNING,
    RunControlState.STOP_REQUESTED,
)


def _naive_now(moment: datetime | None = None) -> datetime:
    return (moment or datetime.now(UTC)).replace(tzinfo=None)


def _owner_pid(attempt: ExecutionAttempt | None) -> int | None:
    if attempt is None or attempt.worker_runtime_ref is None:
        return None
    ref = attempt.worker_runtime_ref
    if not ref.startswith("pid:"):
        return None
    try:
        return int(ref.removeprefix("pid:"))
    except ValueError:
        return None


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


async def _finalize(
    session: AsyncSession,
    run: Run,
    attempt: ExecutionAttempt | None,
    moment: datetime,
    result: EngineResult,
) -> None:
    if (
        result.outcome is EngineOutcome.WAITING_FOR_HUMAN
        and result.interaction is not None
        and run.control_state is not RunControlState.STOP_REQUESTED
        and (
            run.control_state is RunControlState.WAITING_FOR_HUMAN
            or can_transition_run(run.control_state, RunControlState.WAITING_FOR_HUMAN)
        )
    ):
        await _finish_waiting(session, run, attempt, moment, result.interaction)
        return
    if result.outcome is EngineOutcome.COMPLETED_VERIFIED:
        target = RunControlState.COMPLETED
    elif result.outcome is EngineOutcome.STOPPED_SAFE or (
        result.outcome is EngineOutcome.WAITING_FOR_HUMAN
        and run.control_state is RunControlState.STOP_REQUESTED
    ):
        target = RunControlState.STOPPED
    else:
        target = RunControlState.FAILED
    if not can_transition_run(run.control_state, target):
        target = RunControlState.FAILED
    if target is RunControlState.COMPLETED:
        run.control_state = next_run_state(run.control_state, target)
        run.completed_at = moment
        await append_event(
            session,
            run,
            event_type="RUN_COMPLETED",
            category="RUN",
            summary="Run completed; recorded during reconciliation.",
        )
        return
    if target is RunControlState.STOPPED:
        run.control_state = next_run_state(run.control_state, target)
        await append_event(
            session,
            run,
            event_type="RUN_STOPPED",
            category="RUN",
            summary="Run stopped safely; recorded during reconciliation.",
        )
        return
    if result.outcome is EngineOutcome.TERMINAL_UNVERIFIED_OR_INCOMPLETE:
        failure_code = "ENGINE_UNVERIFIED"
        failure_summary = (
            result.failure_summary or "Engine finished without verified completion."
        )
        recoverability = Recoverability.RESUMABLE
    elif result.outcome is EngineOutcome.COMPLETED_VERIFIED:
        failure_code = "ENGINE_UNVERIFIED"
        failure_summary = (
            "Native state shows completion that the Run state could not accept."
        )
        recoverability = Recoverability.RESUMABLE
    else:
        failure_code = "ENGINE_FAILED"
        failure_summary = result.failure_summary or "Engine failed."
        recoverability = Recoverability.UNKNOWN
    run.control_state = next_run_state(run.control_state, target)
    run.failure_class = "ENGINE_FAILURE"
    run.failure_code = failure_code
    run.failure_summary = failure_summary
    run.recoverability = recoverability
    await append_event(
        session,
        run,
        event_type="RUN_FAILED",
        category="RUN",
        severity=EventSeverity.WARNING,
        summary=failure_summary,
        payload={"code": failure_code},
    )


async def reconcile(
    session: AsyncSession,
    *,
    engine_factory: EngineFactory,
    now: datetime | None = None,
) -> int:
    moment = _naive_now(now)
    runs = (
        (
            await session.execute(
                select(Run)
                .where(Run.control_state.in_(ACTIVE_RUN_STATES))
                .order_by(Run.ordinal)
            )
        )
        .scalars()
        .all()
    )
    reconciled = 0
    for run in runs:
        attempt = None
        if run.active_attempt_id is not None:
            attempt = (
                await session.execute(
                    select(ExecutionAttempt).where(
                        ExecutionAttempt.id == run.active_attempt_id
                    )
                )
            ).scalar_one_or_none()
        owner_pid = _owner_pid(attempt)
        if owner_pid is not None and _pid_alive(owner_pid):
            continue
        if attempt is not None and attempt.state not in (
            AttemptState.EXITED,
            AttemptState.LOST,
        ):
            attempt.state = next_attempt_state(attempt.state, AttemptState.LOST)
            attempt.ended_at = moment
            attempt.terminal_reason = "PROCESS_LOST"
            await append_event(
                session,
                run,
                event_type="ATTEMPT_LOST",
                category="ATTEMPT",
                severity=EventSeverity.WARNING,
                summary="Attempt was lost before its outcome was recorded.",
                attempt_id=attempt.id,
            )
        run.active_attempt_id = None
        try:
            engine = await engine_factory(session, run)
            result = engine.inspect_result()
        except EngineError as exc:
            result = EngineResult(
                outcome=EngineOutcome.FAILED, failure_summary=exc.detail
            )
        await _finalize(session, run, attempt, moment, result)
        await leases.force_release(session, project_id=run.project_id)
        run.version += 1
        run.updated_at = moment
        reconciled += 1
        logger.info(
            "reconciled run",
            extra={"run_id": run.id, "state": run.control_state.value},
        )
    reconciled += await _repair_waiting_runs(
        session, engine_factory=engine_factory, moment=moment
    )
    if reconciled:
        await session.commit()
    return reconciled


async def _repair_waiting_runs(
    session: AsyncSession,
    *,
    engine_factory: EngineFactory,
    moment: datetime,
) -> int:
    """Keep Runs waiting for human input consistent across restarts.

    A waiting Run must point at its open interaction; if the interaction is
    missing, the durable native state decides what happens next.
    """
    runs = (
        (
            await session.execute(
                select(Run)
                .where(Run.control_state == RunControlState.WAITING_FOR_HUMAN)
                .order_by(Run.ordinal)
            )
        )
        .scalars()
        .all()
    )
    repaired = 0
    for run in runs:
        pending = await interactions_repo.open_for_run(session, run.id)
        if pending is not None:
            if run.pending_interaction_id != pending.id:
                run.pending_interaction_id = pending.id
                run.version += 1
                run.updated_at = moment
                repaired += 1
            continue
        try:
            engine = await engine_factory(session, run)
            result = engine.inspect_result()
        except EngineError as exc:
            result = EngineResult(
                outcome=EngineOutcome.FAILED, failure_summary=exc.detail
            )
        await _finalize(session, run, None, moment, result)
        run.version += 1
        run.updated_at = moment
        repaired += 1
        logger.info(
            "repaired waiting run",
            extra={"run_id": run.id, "state": run.control_state.value},
        )
    return repaired
