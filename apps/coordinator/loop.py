import logging
import os
from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from domain.states import (
    AttemptState,
    EventSeverity,
    EventSource,
    Recoverability,
    RunControlState,
)
from domain.transitions import next_attempt_state, next_run_state
from engine.base import Engine, EngineEvent, EngineOutcome, EngineRunRequest
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


class _RunEventSink:
    def __init__(self, session: AsyncSession, run: Run, attempt_id: str) -> None:
        self._session = session
        self._run = run
        self._attempt_id = attempt_id

    async def on_event(self, event: EngineEvent) -> None:
        stage = event.stage
        await append_event(
            self._session,
            self._run,
            event_type=event.event_type,
            category=event.category,
            summary=event.summary,
            source=EventSource.ENGINE_ADAPTER,
            severity=event.severity,
            attempt_id=self._attempt_id,
            source_event_sequence=event.source_event_sequence,
            payload=dict(event.payload) if event.payload else None,
            stage_category=stage.category.value if stage else None,
            stage_native_id=stage.native_id if stage else None,
            stage_label=stage.display_label if stage else None,
            stage_order=stage.order if stage else None,
            occurred_at=event.occurred_at,
        )


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
        request = EngineRunRequest(
            project_id=run.project_id, run_id=run.id, attempt_id=attempt.id
        )
        result = await engine.run(request, _RunEventSink(session, run, attempt.id))
        attempt.state = next_attempt_state(attempt.state, AttemptState.EXITED)
        attempt.ended_at = moment
        attempt.terminal_reason = "ENGINE_OUTCOME"

        run.active_attempt_id = None
        if result.outcome is EngineOutcome.COMPLETED_VERIFIED:
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
            if result.outcome is EngineOutcome.TERMINAL_UNVERIFIED_OR_INCOMPLETE:
                failure_code = "ENGINE_UNVERIFIED"
                failure_summary = (
                    result.failure_summary
                    or "Engine finished without verified completion."
                )
            else:
                failure_code = "ENGINE_FAILED"
                failure_summary = result.failure_summary or "Run failed."
            run.control_state = next_run_state(
                run.control_state, RunControlState.FAILED
            )
            run.failure_class = "ENGINE_FAILURE"
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
    engine_factory: Callable[[], Engine],
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
