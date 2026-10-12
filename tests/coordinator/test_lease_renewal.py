import asyncio

from factories import static_factory
from sqlalchemy import select

from coordinator.active import ActiveRun, ActiveRuns
from coordinator.leases import renew_active_leases
from coordinator.loop import drive_run, process_queued_runs
from domain.states import RunControlState
from engine.base import (
    EngineCapabilities,
    EngineDescriptor,
    EngineIdentity,
    EngineOutcome,
    EngineResult,
)
from engine.fake import FakeEngine
from persistence import leases
from persistence.base import Base
from persistence.db import create_db_engine, create_session_factory
from persistence.models import (
    Principal,
    Project,
    ProjectExecutionLease,
    Run,
)


class LeaseStealingEngine:
    def __init__(self, database_url: str) -> None:
        self._database_url = database_url

    def describe(self) -> EngineDescriptor:
        return EngineDescriptor(
            identity=EngineIdentity(family="FAKE", revision="1", adapter_version="1"),
            capabilities=EngineCapabilities(),
        )

    def request_safe_stop(self) -> None:
        return

    def inspect_result(self) -> EngineResult:
        return EngineResult(outcome=EngineOutcome.COMPLETED_VERIFIED)

    async def run(self, request, hooks) -> EngineResult:
        engine = create_db_engine(self._database_url)
        factory = create_session_factory(engine)
        try:
            async with factory() as session:
                lease = (
                    await session.execute(select(ProjectExecutionLease))
                ).scalar_one()
                lease.holder_id = "other"
                lease.lease_epoch += 1
                await session.commit()
        finally:
            await engine.dispose()
        return EngineResult(outcome=EngineOutcome.COMPLETED_VERIFIED)


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


def test_renew_active_leases_renews_held_lease(tmp_path):
    async def scenario():
        engine = await prepare(f"sqlite+aiosqlite:///{tmp_path / 'lease1.db'}")
        factory = create_session_factory(engine)
        try:
            async with factory() as session:
                run = await seed_queued_run(session)
                lease = await leases.acquire(
                    session,
                    project_id=run.project_id,
                    holder_id="coordinator-test",
                    run_id=run.id,
                )
                await session.commit()
                before = lease.expires_at
                run_id = run.id
                project_id = run.project_id

            active = ActiveRuns()
            entry = active.register(run_id)
            entry.project_id = project_id
            entry.holder_id = "coordinator-test"
            entry.lease_epoch = 1
            async with factory() as session:
                renewed = await renew_active_leases(session, active)
                assert renewed == 1

            async with factory() as session:
                stored = (
                    await session.execute(select(ProjectExecutionLease))
                ).scalar_one()
                assert stored.expires_at > before
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_renew_active_leases_signals_when_lease_lost(tmp_path):
    async def scenario():
        engine = await prepare(f"sqlite+aiosqlite:///{tmp_path / 'lease2.db'}")
        factory = create_session_factory(engine)
        try:
            async with factory() as session:
                run = await seed_queued_run(session)
                lease = await leases.acquire(
                    session,
                    project_id=run.project_id,
                    holder_id="coordinator-test",
                    run_id=run.id,
                )
                lease.holder_id = "other"
                lease.lease_epoch += 1
                await session.commit()
                run_id = run.id
                project_id = run.project_id

            active = ActiveRuns()
            entry = active.register(run_id)
            entry.project_id = project_id
            entry.holder_id = "coordinator-test"
            entry.lease_epoch = 1
            async with factory() as session:
                renewed = await renew_active_leases(session, active)
                assert renewed == 0

            assert entry.signal.is_set()
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_renew_active_leases_skips_entries_without_lease(tmp_path):
    async def scenario():
        engine = await prepare(f"sqlite+aiosqlite:///{tmp_path / 'lease3.db'}")
        factory = create_session_factory(engine)
        try:
            active = ActiveRuns()
            active.register("run-without-lease")
            async with factory() as session:
                renewed = await renew_active_leases(session, active)
                assert renewed == 0
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_drive_run_records_lease_scope(tmp_path):
    async def scenario():
        engine = await prepare(f"sqlite+aiosqlite:///{tmp_path / 'lease4.db'}")
        factory = create_session_factory(engine)
        try:
            async with factory() as session:
                run = await seed_queued_run(session)
                await session.commit()
                run_id = run.id
                project_id = run.project_id

            entry = ActiveRun()
            async with factory() as session:
                run = (
                    await session.execute(select(Run).where(Run.id == run_id))
                ).scalar_one()
                await drive_run(
                    session,
                    run,
                    static_factory(FakeEngine()),
                    holder_id="test",
                    active=entry,
                )

            assert entry.project_id == project_id
            assert entry.holder_id == "test"
            assert entry.lease_epoch == 1
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_lost_lease_does_not_lose_outcome(tmp_path):
    async def scenario():
        database_url = f"sqlite+aiosqlite:///{tmp_path / 'lease5.db'}"
        engine = await prepare(database_url)
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
                    engine_factory=static_factory(LeaseStealingEngine(database_url)),
                )
                assert processed == 1

            async with factory() as session:
                run = (
                    await session.execute(select(Run).where(Run.id == run_id))
                ).scalar_one()
                assert run.control_state is RunControlState.COMPLETED
                lease = (
                    await session.execute(select(ProjectExecutionLease))
                ).scalar_one()
                assert lease.holder_id == "other"
        finally:
            await engine.dispose()

    asyncio.run(scenario())
