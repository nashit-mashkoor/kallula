import asyncio

from sqlalchemy import select

from coordinator.loop import process_queued_runs
from domain.states import EventSeverity, EventSource
from engine.fake import FakeEngine, FakeScenario
from persistence.base import Base
from persistence.db import create_db_engine, create_session_factory
from persistence.models import Event, Principal, Project, Run

LIFECYCLE = [
    "RUN_STARTING",
    "ATTEMPT_ALLOCATED",
    "ATTEMPT_STARTED",
    "RUN_STARTED",
    "ATTEMPT_EXITED",
    "RUN_COMPLETED",
]


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


def test_run_lifecycle_emits_ordered_events(tmp_path):
    async def scenario():
        engine = await prepare(f"sqlite+aiosqlite:///{tmp_path / 'events.db'}")
        factory = create_session_factory(engine)
        try:
            async with factory() as session:
                run = await seed_queued_run(session)
                await session.commit()
                run_id = run.id

            async with factory() as session:
                assert await process_queued_runs(session, holder_id="test") == 1

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
                assert [event.sequence for event in events] == [1, 2, 3, 4, 5, 6]
                assert all(
                    event.source is EventSource.RUN_COORDINATOR for event in events
                )
                assert all(event.severity is EventSeverity.INFO for event in events)

                run = (
                    await session.execute(select(Run).where(Run.id == run_id))
                ).scalar_one()
                assert run.last_event_sequence == 6
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_failure_emits_error_event(tmp_path):
    async def scenario():
        engine = await prepare(f"sqlite+aiosqlite:///{tmp_path / 'events.db'}")
        factory = create_session_factory(engine)
        try:
            async with factory() as session:
                run = await seed_queued_run(session)
                await session.commit()
                run_id = run.id

            async with factory() as session:
                await process_queued_runs(
                    session,
                    holder_id="test",
                    engine_factory=lambda: FakeEngine(
                        FakeScenario.FAIL_DURING_EXECUTION
                    ),
                )

            async with factory() as session:
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
                assert last.severity is EventSeverity.ERROR
                assert last.summary
        finally:
            await engine.dispose()

    asyncio.run(scenario())
