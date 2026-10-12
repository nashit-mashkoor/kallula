import asyncio

from factories import static_factory
from sqlalchemy import select

from coordinator.active import ActiveRuns
from coordinator.commands import process_commands
from coordinator.loop import drive_run, process_queued_runs
from domain.states import CommandState, RunControlState
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
from persistence.models import (
    Command,
    Event,
    ExecutionAttempt,
    Principal,
    Project,
    Run,
)


class StoppableEngine:
    def __init__(self) -> None:
        self.started = asyncio.Event()
        self.stop_requested = False

    def describe(self) -> EngineDescriptor:
        return EngineDescriptor(
            identity=EngineIdentity(family="FAKE", revision="1", adapter_version="1"),
            capabilities=EngineCapabilities(safe_stop=True),
        )

    def request_safe_stop(self) -> None:
        self.stop_requested = True

    async def run(self, request, hooks) -> EngineResult:
        self.started.set()
        for _ in range(500):
            if self.stop_requested:
                return EngineResult(outcome=EngineOutcome.STOPPED_SAFE)
            await asyncio.sleep(0.01)
        return EngineResult(
            outcome=EngineOutcome.FAILED, failure_summary="never stopped"
        )


class CompletingEngine:
    def describe(self) -> EngineDescriptor:
        return EngineDescriptor(
            identity=EngineIdentity(family="FAKE", revision="1", adapter_version="1"),
            capabilities=EngineCapabilities(),
        )

    def request_safe_stop(self) -> None:
        return

    async def run(self, request, hooks) -> EngineResult:
        await asyncio.sleep(0.05)
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


def test_stop_scenario_maps_run_to_stopped(tmp_path):
    async def scenario():
        engine = await prepare(f"sqlite+aiosqlite:///{tmp_path / 'stop.db'}")
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
                assert run.failure_code is None

                attempt = (await session.execute(select(ExecutionAttempt))).scalar_one()
                assert attempt.terminal_reason == "SAFE_STOP"

                event_types = [
                    event.event_type
                    for event in (
                        await session.execute(
                            select(Event)
                            .where(Event.run_id == run_id)
                            .order_by(Event.sequence)
                        )
                    )
                    .scalars()
                    .all()
                ]
                assert "RUN_STOPPED" in event_types
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_stop_signal_reaches_running_engine(tmp_path):
    async def scenario():
        engine = await prepare(f"sqlite+aiosqlite:///{tmp_path / 'signal.db'}")
        factory = create_session_factory(engine)
        try:
            async with factory() as session:
                run = await seed_queued_run(session)
                await session.commit()
                run_id = run.id

            stopper = StoppableEngine()
            signal = asyncio.Event()
            async with factory() as session:
                run = (
                    await session.execute(select(Run).where(Run.id == run_id))
                ).scalar_one()
                drive = asyncio.create_task(
                    drive_run(
                        session,
                        run,
                        static_factory(stopper),
                        holder_id="test",
                        stop_signal=signal,
                    )
                )
                await asyncio.wait_for(stopper.started.wait(), timeout=5)
                signal.set()
                await asyncio.wait_for(drive, timeout=10)

            assert stopper.stop_requested is True
            async with factory() as session:
                run = (
                    await session.execute(select(Run).where(Run.id == run_id))
                ).scalar_one()
                assert run.control_state is RunControlState.STOPPED
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_stop_does_not_override_completion(tmp_path):
    async def scenario():
        engine = await prepare(f"sqlite+aiosqlite:///{tmp_path / 'race.db'}")
        factory = create_session_factory(engine)
        try:
            async with factory() as session:
                run = await seed_queued_run(session)
                await session.commit()
                run_id = run.id

            signal = asyncio.Event()
            signal.set()
            async with factory() as session:
                run = (
                    await session.execute(select(Run).where(Run.id == run_id))
                ).scalar_one()
                await drive_run(
                    session,
                    run,
                    static_factory(CompletingEngine()),
                    holder_id="test",
                    stop_signal=signal,
                )

            async with factory() as session:
                run = (
                    await session.execute(select(Run).where(Run.id == run_id))
                ).scalar_one()
                assert run.control_state is RunControlState.COMPLETED
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_process_commands_signals_active_run(tmp_path):
    async def scenario():
        engine = await prepare(f"sqlite+aiosqlite:///{tmp_path / 'commands.db'}")
        factory = create_session_factory(engine)
        try:
            async with factory() as session:
                run = await seed_queued_run(session)
                principal = (await session.execute(select(Principal))).scalars().first()
                await session.flush()
                command = Command(
                    actor_principal_id=principal.id,
                    command_type="SAFE_STOP_RUN",
                    target_type="RUN",
                    target_id=run.id,
                    state=CommandState.ACCEPTED,
                    request_json={"mode": "SAFE"},
                    request_hash="hash",
                    idempotency_key="stop-key",
                )
                session.add(command)
                await session.commit()
                command_id = command.id
                run_id = run.id

            active = ActiveRuns()
            signal = active.register(run_id)
            async with factory() as session:
                applied = await process_commands(session, active=active)
                assert applied == 1

            async with factory() as session:
                stored = (
                    await session.execute(
                        select(Command).where(Command.id == command_id)
                    )
                ).scalar_one()
                assert stored.state is CommandState.APPLIED
                assert stored.applied_at is not None
            assert signal.is_set()
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_process_commands_without_active_run_applies(tmp_path):
    async def scenario():
        engine = await prepare(f"sqlite+aiosqlite:///{tmp_path / 'commands2.db'}")
        factory = create_session_factory(engine)
        try:
            async with factory() as session:
                run = await seed_queued_run(session)
                principal = (await session.execute(select(Principal))).scalars().first()
                command = Command(
                    actor_principal_id=principal.id,
                    command_type="SAFE_STOP_RUN",
                    target_type="RUN",
                    target_id=run.id,
                    state=CommandState.ACCEPTED,
                    request_json={"mode": "SAFE"},
                    request_hash="hash",
                    idempotency_key="stop-key-2",
                )
                session.add(command)
                await session.commit()
                command_id = command.id

            async with factory() as session:
                applied = await process_commands(session, active=ActiveRuns())
                assert applied == 1

            async with factory() as session:
                stored = (
                    await session.execute(
                        select(Command).where(Command.id == command_id)
                    )
                ).scalar_one()
                assert stored.state is CommandState.APPLIED
        finally:
            await engine.dispose()

    asyncio.run(scenario())
