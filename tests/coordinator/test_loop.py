import asyncio

from sqlalchemy import select

from coordinator.loop import process_queued_runs
from domain.states import AttemptState, Recoverability, RunControlState
from engine.fake import FakeEngine, FakeScenario
from persistence import leases
from persistence.base import Base
from persistence.db import create_db_engine, create_session_factory
from persistence.models import (
    ExecutionAttempt,
    Principal,
    Project,
    ProjectExecutionLease,
    Run,
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


def test_queued_run_completes(tmp_path):
    async def scenario():
        engine = await prepare(f"sqlite+aiosqlite:///{tmp_path / 'loop.db'}")
        factory = create_session_factory(engine)
        try:
            async with factory() as session:
                run = await seed_queued_run(session)
                await session.commit()
                run_id = run.id

            async with factory() as session:
                processed = await process_queued_runs(
                    session, holder_id="test", engine_factory=FakeEngine
                )
                assert processed == 1

            async with factory() as session:
                stored = (
                    await session.execute(select(Run).where(Run.id == run_id))
                ).scalar_one()
                assert stored.control_state is RunControlState.COMPLETED
                assert stored.completed_at is not None
                assert stored.active_attempt_id is None

                attempt = (await session.execute(select(ExecutionAttempt))).scalar_one()
                assert attempt.state is AttemptState.EXITED
                assert attempt.terminal_reason == "ENGINE_OUTCOME"

                lease = (
                    await session.execute(select(ProjectExecutionLease))
                ).scalar_one_or_none()
                assert lease is None
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_failure_scenario_marks_run_failed(tmp_path):
    async def scenario():
        engine = await prepare(f"sqlite+aiosqlite:///{tmp_path / 'loop.db'}")
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
                    engine_factory=lambda: FakeEngine(
                        FakeScenario.FAIL_DURING_EXECUTION
                    ),
                )
                assert processed == 1

            async with factory() as session:
                stored = (
                    await session.execute(select(Run).where(Run.id == run_id))
                ).scalar_one()
                assert stored.control_state is RunControlState.FAILED
                assert stored.failure_code == "ENGINE_FAILED"
                assert stored.recoverability is Recoverability.UNKNOWN
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_processing_is_idempotent_across_restarts(tmp_path):
    async def scenario():
        engine = await prepare(f"sqlite+aiosqlite:///{tmp_path / 'loop.db'}")
        factory = create_session_factory(engine)
        try:
            async with factory() as session:
                run = await seed_queued_run(session)
                await session.commit()
                run_id = run.id

            async with factory() as session:
                assert (
                    await process_queued_runs(
                        session, holder_id="first", engine_factory=FakeEngine
                    )
                    == 1
                )

            async with factory() as session:
                assert (
                    await process_queued_runs(
                        session, holder_id="second", engine_factory=FakeEngine
                    )
                    == 0
                )

            async with factory() as session:
                stored = (
                    await session.execute(select(Run).where(Run.id == run_id))
                ).scalar_one()
                assert stored.control_state is RunControlState.COMPLETED
                attempts = (
                    (await session.execute(select(ExecutionAttempt))).scalars().all()
                )
                assert len(attempts) == 1
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_run_is_skipped_when_project_lease_is_held(tmp_path):
    async def scenario():
        engine = await prepare(f"sqlite+aiosqlite:///{tmp_path / 'loop.db'}")
        factory = create_session_factory(engine)
        try:
            async with factory() as session:
                run = await seed_queued_run(session)
                await session.commit()
                run_id = run.id
                project_id = run.project_id

            async with factory() as session:
                await leases.acquire(session, project_id=project_id, holder_id="other")
                await session.commit()

            async with factory() as session:
                processed = await process_queued_runs(
                    session, holder_id="test", engine_factory=FakeEngine
                )
                assert processed == 0

            async with factory() as session:
                stored = (
                    await session.execute(select(Run).where(Run.id == run_id))
                ).scalar_one()
                assert stored.control_state is RunControlState.QUEUED
                attempts = (
                    (await session.execute(select(ExecutionAttempt))).scalars().all()
                )
                assert attempts == []
        finally:
            await engine.dispose()

    asyncio.run(scenario())
