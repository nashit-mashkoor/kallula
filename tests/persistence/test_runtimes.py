import asyncio
from datetime import UTC, datetime

from sqlalchemy import select

from domain.states import AttemptState, EngineRuntimeState
from persistence.attempts import create_attempt
from persistence.base import Base
from persistence.db import create_db_engine, create_session_factory
from persistence.models import (
    ExecutionAttempt,
    Principal,
    Project,
    Run,
    RunEngineRuntime,
)
from persistence.runtimes import (
    ensure_run_runtime,
    get_run_runtime,
    runtime_storage_key,
)


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


def test_ensure_run_runtime_creates_and_reuses_runtime(tmp_path):
    async def scenario():
        engine = await prepare(f"sqlite+aiosqlite:///{tmp_path / 'runtimes.db'}")
        factory = create_session_factory(engine)
        try:
            async with factory() as session:
                run = await seed_run(session)
                runtime = await ensure_run_runtime(session, run)
                await session.commit()
                runtime_id = runtime.id
                assert runtime.state is EngineRuntimeState.INITIALIZING
                assert runtime.storage_driver == "local"
                assert (
                    runtime.storage_key
                    == f"projects/{run.project_id}/runs/{run.id}/engine-runtime"
                )
                assert runtime.storage_key == runtime_storage_key(run)

            async with factory() as session:
                run = (await session.execute(select(Run))).scalar_one()
                again = await ensure_run_runtime(session, run)
                await session.commit()
                assert again.id == runtime_id
                stored = (
                    (await session.execute(select(RunEngineRuntime))).scalars().all()
                )
                assert len(stored) == 1
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_runtime_persists_across_attempt_lifecycle(tmp_path):
    async def scenario():
        engine = await prepare(f"sqlite+aiosqlite:///{tmp_path / 'lifecycle.db'}")
        factory = create_session_factory(engine)
        try:
            async with factory() as session:
                run = await seed_run(session)
                runtime = await ensure_run_runtime(session, run)
                runtime.state = EngineRuntimeState.READY
                runtime.validated_at = datetime.now(UTC)
                attempt = await create_attempt(session, run)
                await session.commit()
                runtime_id = runtime.id
                attempt_id = attempt.id

            async with factory() as session:
                attempt = (
                    await session.execute(
                        select(ExecutionAttempt).where(
                            ExecutionAttempt.id == attempt_id
                        )
                    )
                ).scalar_one()
                attempt.state = AttemptState.EXITED
                attempt.ended_at = datetime.now(UTC)
                attempt.terminal_reason = "ENGINE_OUTCOME"
                await session.commit()

            async with factory() as session:
                run = (await session.execute(select(Run))).scalar_one()
                stored = await get_run_runtime(session, run.id)
                assert stored is not None
                assert stored.id == runtime_id
                assert stored.state is EngineRuntimeState.READY
                assert stored.validated_at is not None
                attempts = (
                    (await session.execute(select(ExecutionAttempt))).scalars().all()
                )
                assert attempts[0].state is AttemptState.EXITED
        finally:
            await engine.dispose()

    asyncio.run(scenario())
