import asyncio

from factories import static_factory
from sqlalchemy import select

from coordinator.loop import process_queued_runs
from domain.states import AttemptState, RunControlState
from engine.fake import FakeEngine, FakeScenario
from persistence.base import Base
from persistence.db import create_db_engine, create_session_factory
from persistence.models import ExecutionAttempt, Principal, Project, Run


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


def test_resumed_run_creates_new_attempt(tmp_path):
    async def scenario():
        engine = await prepare(f"sqlite+aiosqlite:///{tmp_path / 'resume.db'}")
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
                    engine_factory=static_factory(
                        FakeEngine(FakeScenario.STOP_AT_SAFE_BOUNDARY)
                    ),
                )
                assert processed == 1

            async with factory() as session:
                run = (
                    await session.execute(select(Run).where(Run.id == run_id))
                ).scalar_one()
                assert run.control_state is RunControlState.STOPPED
                run.control_state = RunControlState.QUEUED
                await session.commit()

            async with factory() as session:
                processed = await process_queued_runs(
                    session,
                    holder_id="test",
                    engine_factory=static_factory(FakeEngine()),
                )
                assert processed == 1

            async with factory() as session:
                run = (
                    await session.execute(select(Run).where(Run.id == run_id))
                ).scalar_one()
                assert run.control_state is RunControlState.COMPLETED
                attempts = (
                    (
                        await session.execute(
                            select(ExecutionAttempt).order_by(ExecutionAttempt.ordinal)
                        )
                    )
                    .scalars()
                    .all()
                )
                assert [attempt.ordinal for attempt in attempts] == [1, 2]
                assert attempts[0].terminal_reason == "SAFE_STOP"
                assert attempts[1].state is AttemptState.EXITED
        finally:
            await engine.dispose()

    asyncio.run(scenario())
