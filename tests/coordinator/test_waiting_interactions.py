import asyncio

from factories import static_factory
from sqlalchemy import select

from coordinator.loop import (
    engine_interaction_response,
    process_queued_runs,
    settle_stop_requested_runs,
)
from coordinator.reconcile import reconcile
from domain.states import (
    AttemptState,
    InteractionKind,
    InteractionResponseType,
    InteractionState,
    RunControlState,
)
from engine.base import EngineInteractionResponse
from engine.fake import FakeEngine, FakeScenario
from persistence.base import Base
from persistence.db import create_db_engine, create_session_factory
from persistence.models import (
    Event,
    ExecutionAttempt,
    InteractionResponse,
    PendingInteraction,
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


async def event_types(session, run_id: str) -> list[str]:
    return [
        event.event_type
        for event in (
            await session.execute(
                select(Event).where(Event.run_id == run_id).order_by(Event.sequence)
            )
        )
        .scalars()
        .all()
    ]


def test_engine_waiting_suspends_run_and_opens_interaction(tmp_path):
    async def scenario():
        engine = await prepare(f"sqlite+aiosqlite:///{tmp_path / 'wait.db'}")
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
                        FakeEngine(FakeScenario.WAIT_FOR_HUMAN)
                    ),
                )
                assert processed == 1

            async with factory() as session:
                stored = (
                    await session.execute(select(Run).where(Run.id == run_id))
                ).scalar_one()
                assert stored.control_state is RunControlState.WAITING_FOR_HUMAN
                assert stored.pending_interaction_id is not None
                assert stored.active_attempt_id is None

                attempt = (await session.execute(select(ExecutionAttempt))).scalar_one()
                assert attempt.state is AttemptState.EXITED
                assert attempt.terminal_reason == "WAITING_FOR_HUMAN"

                interaction = (
                    await session.execute(select(PendingInteraction))
                ).scalar_one()
                assert interaction.id == stored.pending_interaction_id
                assert interaction.status is InteractionState.OPEN
                assert interaction.kind is InteractionKind.QUESTION
                assert interaction.prompt == "Which UI?"
                assert interaction.recommendation == "menu bar"
                assert interaction.engine_interaction_token == "native-interaction-1"
                assert interaction.allowed_responses_json == [
                    "ANSWER",
                    "USE_RECOMMENDATION",
                    "DELEGATE_REMAINING",
                ]

                assert await event_types(session, run_id) == [
                    "RUN_STARTING",
                    "ATTEMPT_ALLOCATED",
                    "ATTEMPT_STARTED",
                    "RUN_STARTED",
                    "ATTEMPT_EXITED",
                    "RUN_WAITING_FOR_HUMAN",
                    "INTERACTION_OPENED",
                ]

                lease = (
                    await session.execute(select(ProjectExecutionLease))
                ).scalar_one_or_none()
                assert lease is None
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_accepted_answer_continues_as_new_attempt(tmp_path):
    async def scenario():
        engine = await prepare(f"sqlite+aiosqlite:///{tmp_path / 'resume.db'}")
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
                    engine_factory=static_factory(
                        FakeEngine(FakeScenario.WAIT_FOR_HUMAN)
                    ),
                )

            # the answer command's atomic effects (API section 81.2)
            async with factory() as session:
                run = (
                    await session.execute(select(Run).where(Run.id == run_id))
                ).scalar_one()
                interaction = (
                    await session.execute(select(PendingInteraction))
                ).scalar_one()
                principal = (await session.execute(select(Principal))).scalar_one()
                interaction.status = InteractionState.ANSWERED
                session.add(
                    InteractionResponse(
                        interaction_id=interaction.id,
                        run_id=run_id,
                        actor_principal_id=principal.id,
                        response_type=InteractionResponseType.ANSWER,
                        answer_text="menu bar",
                    )
                )
                run.control_state = RunControlState.QUEUED
                run.pending_interaction_id = None
                await session.commit()

            async with factory() as session:
                processed = await process_queued_runs(
                    session,
                    holder_id="test",
                    engine_factory=static_factory(
                        FakeEngine(FakeScenario.WAIT_FOR_HUMAN)
                    ),
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
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_same_native_question_is_reused_not_duplicated(tmp_path):
    async def scenario():
        engine = await prepare(f"sqlite+aiosqlite:///{tmp_path / 'reuse.db'}")
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
                    engine_factory=static_factory(
                        FakeEngine(FakeScenario.WAIT_FOR_HUMAN)
                    ),
                )
            # a resume without an answer re-waits on the same native question
            async with factory() as session:
                run = (
                    await session.execute(select(Run).where(Run.id == run_id))
                ).scalar_one()
                run.control_state = RunControlState.QUEUED
                await session.commit()
            async with factory() as session:
                await process_queued_runs(
                    session,
                    holder_id="test",
                    engine_factory=static_factory(
                        FakeEngine(FakeScenario.WAIT_FOR_HUMAN)
                    ),
                )

            async with factory() as session:
                interactions = (
                    (await session.execute(select(PendingInteraction))).scalars().all()
                )
                assert len(interactions) == 1
                assert interactions[0].status is InteractionState.OPEN
                assert await event_types(session, run_id) == [
                    "RUN_STARTING",
                    "ATTEMPT_ALLOCATED",
                    "ATTEMPT_STARTED",
                    "RUN_STARTED",
                    "ATTEMPT_EXITED",
                    "RUN_WAITING_FOR_HUMAN",
                    "INTERACTION_OPENED",
                    "RUN_STARTING",
                    "ATTEMPT_ALLOCATED",
                    "ATTEMPT_STARTED",
                    "RUN_STARTED",
                    "ATTEMPT_EXITED",
                    "RUN_WAITING_FOR_HUMAN",
                ]
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_reconcile_repairs_waiting_run_without_open_interaction(tmp_path):
    async def scenario():
        engine = await prepare(f"sqlite+aiosqlite:///{tmp_path / 'repair.db'}")
        factory = create_session_factory(engine)
        try:
            async with factory() as session:
                run = await seed_queued_run(session)
                run.control_state = RunControlState.WAITING_FOR_HUMAN
                await session.commit()
                run_id = run.id

            async with factory() as session:
                repaired = await reconcile(
                    session,
                    engine_factory=static_factory(
                        FakeEngine(FakeScenario.WAIT_FOR_HUMAN)
                    ),
                )
                assert repaired == 1

            async with factory() as session:
                run = (
                    await session.execute(select(Run).where(Run.id == run_id))
                ).scalar_one()
                assert run.control_state is RunControlState.WAITING_FOR_HUMAN
                interaction = (
                    await session.execute(select(PendingInteraction))
                ).scalar_one()
                assert run.pending_interaction_id == interaction.id
                assert interaction.status is InteractionState.OPEN
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_stop_request_without_worker_settles_stopped(tmp_path):
    async def scenario():
        engine = await prepare(f"sqlite+aiosqlite:///{tmp_path / 'stop.db'}")
        factory = create_session_factory(engine)
        try:
            async with factory() as session:
                run = await seed_queued_run(session)
                await session.commit()
                run_id = run.id
            async with factory() as session:
                run = (
                    await session.execute(select(Run).where(Run.id == run_id))
                ).scalar_one()
                run.control_state = RunControlState.STOP_REQUESTED
                await session.commit()

            async with factory() as session:
                settled = await settle_stop_requested_runs(session)
                assert settled == 1

            async with factory() as session:
                run = (
                    await session.execute(select(Run).where(Run.id == run_id))
                ).scalar_one()
                assert run.control_state is RunControlState.STOPPED
                assert "RUN_STOPPED" in await event_types(session, run_id)
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_stop_request_with_active_attempt_is_left_alone(tmp_path):
    async def scenario():
        engine = await prepare(f"sqlite+aiosqlite:///{tmp_path / 'stop2.db'}")
        factory = create_session_factory(engine)
        try:
            async with factory() as session:
                run = await seed_queued_run(session)
                await session.flush()
                attempt = ExecutionAttempt(
                    run_id=run.id,
                    ordinal=1,
                    state=AttemptState.ACTIVE,
                )
                session.add(attempt)
                await session.flush()
                run.active_attempt_id = attempt.id
                run.control_state = RunControlState.STOP_REQUESTED
                await session.commit()
                run_id = run.id

            async with factory() as session:
                settled = await settle_stop_requested_runs(session)
                assert settled == 0

            async with factory() as session:
                run = (
                    await session.execute(select(Run).where(Run.id == run_id))
                ).scalar_one()
                assert run.control_state is RunControlState.STOP_REQUESTED
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_engine_response_mapping():
    interaction = PendingInteraction(
        id="i-1",
        run_id="r-1",
        kind=InteractionKind.QUESTION,
        status=InteractionState.OPEN,
        title="Requirements question",
        prompt="Which UI?",
        recommendation="menu bar",
        engine_interaction_token="native-9",
    )

    def response(response_type: InteractionResponseType, answer: str | None):
        return InteractionResponse(
            interaction_id="i-1",
            run_id="r-1",
            actor_principal_id="p-1",
            response_type=response_type,
            answer_text=answer,
        )

    mapped = engine_interaction_response(
        response(InteractionResponseType.ANSWER, "terminal"), interaction
    )
    assert mapped == EngineInteractionResponse(
        interaction_id="native-9", kind="QUESTION", accept=False, answer="terminal"
    )

    mapped = engine_interaction_response(
        response(InteractionResponseType.USE_RECOMMENDATION, None), interaction
    )
    assert mapped.answer == "menu bar"

    mapped = engine_interaction_response(
        response(InteractionResponseType.DELEGATE_REMAINING, None), interaction
    )
    assert mapped.answer == "auto"

    mapped = engine_interaction_response(
        response(InteractionResponseType.CONFIRM, None), interaction
    )
    assert mapped.accept is True
    assert mapped.answer == ""
