import asyncio

from sqlalchemy import select

from coordinator.loop import process_queued_runs
from domain.states import EventSource, Recoverability, RunControlState
from engine.base import (
    EngineCapabilities,
    EngineDescriptor,
    EngineIdentity,
    EngineOutcome,
    EngineResult,
)
from engine.fake import FakeEngine, FakeScenario
from persistence.base import Base
from persistence.db import create_db_engine, create_session_factory
from persistence.models import Event, ExecutionAttempt, Principal, Project, Run

LIFECYCLE = [
    "RUN_STARTING",
    "ATTEMPT_ALLOCATED",
    "ATTEMPT_STARTED",
    "RUN_STARTED",
    "STAGE_STARTED",
    "WORK_ITEM_STARTED",
    "WORK_ITEM_COMPLETED",
    "STAGE_COMPLETED",
    "ATTEMPT_EXITED",
    "RUN_COMPLETED",
]


class UnverifiedEngine:
    def describe(self) -> EngineDescriptor:
        return EngineDescriptor(
            identity=EngineIdentity(family="FAKE", revision="1", adapter_version="1"),
            capabilities=EngineCapabilities(),
        )

    async def run(self, request, hooks) -> EngineResult:
        return EngineResult(
            outcome=EngineOutcome.TERMINAL_UNVERIFIED_OR_INCOMPLETE,
            failure_summary="Verification did not pass.",
        )


async def prepare(database_url: str):
    engine = create_db_engine(database_url)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    return engine


async def seed_queued_run(session) -> Run:
    principal = Principal(
        auth_provider="development", auth_subject="dev", display_name="Dev"
    )
    session.add(principal)
    await session.flush()
    project = Project(owner_id=principal.id, display_name="Project")
    session.add(project)
    await session.flush()
    run = Run(project_id=project.id, ordinal=1, objective="Build it")
    session.add(run)
    await session.flush()
    return run


def test_engine_events_are_persisted(tmp_path):
    async def scenario():
        engine = await prepare(f"sqlite+aiosqlite:///{tmp_path / 'engine-events.db'}")
        factory = create_session_factory(engine)
        try:
            async with factory() as session:
                run = await seed_queued_run(session)
                await session.commit()
                run_id = run.id

            async with factory() as session:
                processed = await process_queued_runs(
                    session,
                    holder_id="test",
                    engine_factory=lambda: FakeEngine(FakeScenario.EMIT_WORK_ITEMS),
                )
                assert processed == 1

            async with factory() as session:
                events = (
                    (
                        await session.execute(
                            select(Event)
                            .where(Event.run_id == run_id)
                            .order_by(Event.sequence)
                        )
                    )
                    .scalars()
                    .all()
                )
                assert [event.event_type for event in events] == LIFECYCLE

                engine_events = [
                    event
                    for event in events
                    if event.source is EventSource.ENGINE_ADAPTER
                ]
                assert [event.source_event_sequence for event in engine_events] == [
                    1,
                    2,
                    3,
                    4,
                ]
                assert all(
                    event.stage_category == "EXECUTION" for event in engine_events
                )
                assert all(event.stage_label == "Execution" for event in engine_events)
                assert all(event.stage_order == 4 for event in engine_events)

                attempt = (await session.execute(select(ExecutionAttempt))).scalar_one()
                assert all(event.attempt_id == attempt.id for event in engine_events)

                run = (
                    await session.execute(select(Run).where(Run.id == run_id))
                ).scalar_one()
                assert run.control_state is RunControlState.COMPLETED
                assert run.last_event_sequence == 10
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_unverified_outcome_marks_run_failed(tmp_path):
    async def scenario():
        engine = await prepare(
            f"sqlite+aiosqlite:///{tmp_path / 'unverified-engine.db'}"
        )
        factory = create_session_factory(engine)
        try:
            async with factory() as session:
                run = await seed_queued_run(session)
                await session.commit()
                run_id = run.id

            async with factory() as session:
                processed = await process_queued_runs(
                    session, holder_id="test", engine_factory=UnverifiedEngine
                )
                assert processed == 1

            async with factory() as session:
                run = (
                    await session.execute(select(Run).where(Run.id == run_id))
                ).scalar_one()
                assert run.control_state is RunControlState.FAILED
                assert run.failure_class == "ENGINE_FAILURE"
                assert run.failure_code == "ENGINE_UNVERIFIED"
                assert run.failure_summary == "Verification did not pass."
                assert run.recoverability is Recoverability.UNKNOWN

                last = (
                    (
                        await session.execute(
                            select(Event)
                            .where(Event.run_id == run_id)
                            .order_by(Event.sequence.desc())
                        )
                    )
                    .scalars()
                    .first()
                )
                assert last is not None
                assert last.event_type == "RUN_FAILED"
                assert last.payload_json == {"code": "ENGINE_UNVERIFIED"}
        finally:
            await engine.dispose()

    asyncio.run(scenario())
