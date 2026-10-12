import asyncio
import os
from datetime import UTC, datetime, timedelta

from factories import static_factory
from sqlalchemy import select

from coordinator.reconcile import reconcile
from domain.states import (
    AttemptState,
    Recoverability,
    RunControlState,
)
from engine.base import (
    EngineCapabilities,
    EngineDescriptor,
    EngineIdentity,
    EngineOutcome,
    EngineResult,
)
from persistence.base import Base
from persistence.db import create_db_engine, create_session_factory
from persistence.models import (
    ExecutionAttempt,
    Principal,
    Project,
    ProjectExecutionLease,
    Run,
)


class InspectEngine:
    def __init__(self, result: EngineResult) -> None:
        self._result = result

    def describe(self) -> EngineDescriptor:
        return EngineDescriptor(
            identity=EngineIdentity(family="FAKE", revision="1", adapter_version="1"),
            capabilities=EngineCapabilities(),
        )

    def request_safe_stop(self) -> None:
        return

    def inspect_result(self) -> EngineResult:
        return self._result

    async def run(self, request, hooks) -> EngineResult:
        return self._result


async def prepare(database_url: str):
    engine = create_db_engine(database_url)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    return engine


async def seed_active_run(
    session,
    *,
    state: RunControlState = RunControlState.RUNNING,
    owner_pid: int = 999999,
) -> Run:
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
    attempt = ExecutionAttempt(
        run_id=run.id,
        ordinal=1,
        state=AttemptState.ACTIVE,
        worker_runtime_ref=f"pid:{owner_pid}",
    )
    session.add(attempt)
    await session.flush()
    run.control_state = state
    run.active_attempt_id = attempt.id
    moment = datetime.now(UTC).replace(tzinfo=None)
    session.add(
        ProjectExecutionLease(
            project_id=project.id,
            run_id=run.id,
            attempt_id=attempt.id,
            holder_id=f"coordinator-{owner_pid}",
            acquired_at=moment,
            renewed_at=moment,
            expires_at=moment + timedelta(hours=1),
            lease_epoch=1,
        )
    )
    await session.flush()
    return run


def test_reconcile_finalizes_completed_native_state(tmp_path):
    async def scenario():
        engine = await prepare(f"sqlite+aiosqlite:///{tmp_path / 'recon1.db'}")
        factory = create_session_factory(engine)
        try:
            async with factory() as session:
                run = await seed_active_run(session)
                await session.commit()
                run_id = run.id

            async with factory() as session:
                reconciled = await reconcile(
                    session,
                    engine_factory=static_factory(
                        InspectEngine(
                            EngineResult(outcome=EngineOutcome.COMPLETED_VERIFIED)
                        )
                    ),
                )
                assert reconciled == 1

            async with factory() as session:
                run = (
                    await session.execute(select(Run).where(Run.id == run_id))
                ).scalar_one()
                assert run.control_state is RunControlState.COMPLETED
                assert run.failure_code is None
                attempt = (await session.execute(select(ExecutionAttempt))).scalar_one()
                assert attempt.state is AttemptState.LOST
                assert attempt.terminal_reason == "PROCESS_LOST"
                assert (
                    await session.execute(select(ProjectExecutionLease))
                ).scalar_one_or_none() is None
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_reconcile_maps_safe_stop(tmp_path):
    async def scenario():
        engine = await prepare(f"sqlite+aiosqlite:///{tmp_path / 'recon2.db'}")
        factory = create_session_factory(engine)
        try:
            async with factory() as session:
                run = await seed_active_run(
                    session, state=RunControlState.STOP_REQUESTED
                )
                await session.commit()
                run_id = run.id

            async with factory() as session:
                reconciled = await reconcile(
                    session,
                    engine_factory=static_factory(
                        InspectEngine(EngineResult(outcome=EngineOutcome.STOPPED_SAFE))
                    ),
                )
                assert reconciled == 1

            async with factory() as session:
                run = (
                    await session.execute(select(Run).where(Run.id == run_id))
                ).scalar_one()
                assert run.control_state is RunControlState.STOPPED
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_reconcile_maps_unverified_to_resumable(tmp_path):
    async def scenario():
        engine = await prepare(f"sqlite+aiosqlite:///{tmp_path / 'recon3.db'}")
        factory = create_session_factory(engine)
        try:
            async with factory() as session:
                run = await seed_active_run(session)
                await session.commit()
                run_id = run.id

            async with factory() as session:
                reconciled = await reconcile(
                    session,
                    engine_factory=static_factory(
                        InspectEngine(
                            EngineResult(
                                outcome=EngineOutcome.TERMINAL_UNVERIFIED_OR_INCOMPLETE,
                                failure_summary="Verification did not pass.",
                            )
                        )
                    ),
                )
                assert reconciled == 1

            async with factory() as session:
                run = (
                    await session.execute(select(Run).where(Run.id == run_id))
                ).scalar_one()
                assert run.control_state is RunControlState.FAILED
                assert run.failure_code == "ENGINE_UNVERIFIED"
                assert run.recoverability is Recoverability.RESUMABLE
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_reconcile_maps_failure(tmp_path):
    async def scenario():
        engine = await prepare(f"sqlite+aiosqlite:///{tmp_path / 'recon4.db'}")
        factory = create_session_factory(engine)
        try:
            async with factory() as session:
                run = await seed_active_run(session)
                await session.commit()
                run_id = run.id

            async with factory() as session:
                reconciled = await reconcile(
                    session,
                    engine_factory=static_factory(
                        InspectEngine(
                            EngineResult(
                                outcome=EngineOutcome.FAILED,
                                failure_summary="Engine crashed.",
                            )
                        )
                    ),
                )
                assert reconciled == 1

            async with factory() as session:
                run = (
                    await session.execute(select(Run).where(Run.id == run_id))
                ).scalar_one()
                assert run.control_state is RunControlState.FAILED
                assert run.failure_code == "ENGINE_FAILED"
                assert run.recoverability is Recoverability.UNKNOWN
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_reconcile_skips_live_owner(tmp_path):
    async def scenario():
        engine = await prepare(f"sqlite+aiosqlite:///{tmp_path / 'recon5.db'}")
        factory = create_session_factory(engine)
        try:
            async with factory() as session:
                run = await seed_active_run(session, owner_pid=os.getpid())
                await session.commit()
                run_id = run.id

            async with factory() as session:
                reconciled = await reconcile(
                    session,
                    engine_factory=static_factory(
                        InspectEngine(
                            EngineResult(outcome=EngineOutcome.COMPLETED_VERIFIED)
                        )
                    ),
                )
                assert reconciled == 0

            async with factory() as session:
                run = (
                    await session.execute(select(Run).where(Run.id == run_id))
                ).scalar_one()
                assert run.control_state is RunControlState.RUNNING
                assert run.active_attempt_id is not None
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_reconcile_without_active_runs(tmp_path):
    async def scenario():
        engine = await prepare(f"sqlite+aiosqlite:///{tmp_path / 'recon6.db'}")
        factory = create_session_factory(engine)
        try:
            async with factory() as session:
                reconciled = await reconcile(
                    session,
                    engine_factory=static_factory(
                        InspectEngine(
                            EngineResult(outcome=EngineOutcome.COMPLETED_VERIFIED)
                        )
                    ),
                )
                assert reconciled == 0
        finally:
            await engine.dispose()

    asyncio.run(scenario())
