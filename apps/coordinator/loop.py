import logging
import os
from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from domain.states import AttemptState, EventSeverity, Recoverability, RunControlState
from domain.transitions import next_attempt_state, next_run_state
from engine.base import Engine, EngineOutcome
from engine.fake import FakeEngine
from persistence import leases
from persistence.attempts import create_attempt
from persistence.events import append_event
from persistence.models import Run

logger = logging.getLogger("coordinator")

POLL_INTERVAL_SECONDS = 1.0


def default_holder_id() -> str:
    return f"coordinator-{os.getpid()}"


def _naive_now(moment: datetime | None = None) -> datetime:
    return (moment or datetime.now(UTC)).replace(tzinfo=None)


async def drive_run(
    session: AsyncSession,
    run: Run,
    engine: Engine,
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
        result = engine.run()
        attempt.state = next_attempt_state(attempt.state, AttemptState.EXITED)
        attempt.ended_at = moment
        attempt.terminal_reason = "ENGINE_OUTCOME"

        run.active_attempt_id = None
        if result.outcome is EngineOutcome.COMPLETED:
            run.control_state = next_run_state(
                run.control_state, RunControlState.COMPLETED
            )
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
        else:
            run.control_state = next_run_state(
                run.control_state, RunControlState.FAILED
            )
            run.failure_class = "ENGINE_FAILURE"
            run.failure_code = "ENGINE_FAILED"
            run.failure_summary = result.failure_summary
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
                summary=result.failure_summary or "Run failed.",
                payload={"code": "ENGINE_FAILED"},
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
    engine_factory: Callable[[], Engine] = FakeEngine,
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
            await drive_run(
                session, run, engine_factory(), holder_id=holder_id, now=now
            )
            processed += 1
        except leases.LeaseConflictError:
            continue
    return processed
