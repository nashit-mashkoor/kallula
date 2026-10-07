import asyncio

from sqlalchemy import select

from domain.states import EventSource
from persistence.base import Base
from persistence.db import create_db_engine, create_session_factory
from persistence.events import append_event
from persistence.models import Event, Principal, Project, Run


async def prepare(database_url: str):
    engine = create_db_engine(database_url)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    return engine


async def seed_run(session) -> Run:
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


def test_sequences_are_monotonic_and_update_run_projection(tmp_path):
    async def scenario():
        engine = await prepare(f"sqlite+aiosqlite:///{tmp_path / 'append.db'}")
        factory = create_session_factory(engine)
        try:
            async with factory() as session:
                run = await seed_run(session)
                first = await append_event(
                    session,
                    run,
                    event_type="RUN_STARTING",
                    category="RUN",
                    summary="Run is starting.",
                    source=EventSource.RUN_COORDINATOR,
                )
                second = await append_event(
                    session,
                    run,
                    event_type="RUN_STARTED",
                    category="RUN",
                    summary="Run started.",
                    source=EventSource.RUN_COORDINATOR,
                )
                await session.commit()

                assert first.sequence == 1
                assert second.sequence == 2
                assert run.last_event_sequence == 2

            async with factory() as session:
                sequences = (
                    (
                        await session.execute(
                            select(Event.sequence).order_by(Event.sequence)
                        )
                    )
                    .scalars()
                    .all()
                )
                assert sequences == [1, 2]
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_rollback_leaves_no_event_and_no_gap(tmp_path):
    async def scenario():
        engine = await prepare(f"sqlite+aiosqlite:///{tmp_path / 'append.db'}")
        factory = create_session_factory(engine)
        try:
            async with factory() as session:
                await seed_run(session)
                await session.commit()

            async with factory() as session:
                run = (await session.execute(select(Run))).scalar_one()
                await append_event(
                    session,
                    run,
                    event_type="RUN_STARTING",
                    category="RUN",
                    summary="Run is starting.",
                )
                await session.rollback()

            async with factory() as session:
                run = (await session.execute(select(Run))).scalar_one()
                assert run.last_event_sequence == 0
                assert (await session.execute(select(Event))).scalars().all() == []

                event = await append_event(
                    session,
                    run,
                    event_type="RUN_STARTING",
                    category="RUN",
                    summary="Run is starting.",
                )
                await session.commit()
                assert event.sequence == 1
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_append_preserves_payload_and_severity(tmp_path):
    async def scenario():
        engine = await prepare(f"sqlite+aiosqlite:///{tmp_path / 'append.db'}")
        factory = create_session_factory(engine)
        try:
            async with factory() as session:
                run = await seed_run(session)
                event = await append_event(
                    session,
                    run,
                    event_type="TEST_RUN_COMPLETED",
                    category="TESTS",
                    summary="31 tests passed.",
                    payload={"passed": 31, "failed": 0},
                )
                await session.commit()
                assert event.payload_json == {"passed": 31, "failed": 0}
                assert event.payload_version == 1
        finally:
            await engine.dispose()

    asyncio.run(scenario())
