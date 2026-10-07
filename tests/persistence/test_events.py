import asyncio

import pytest
from sqlalchemy import select
from sqlalchemy import text as sql_text
from sqlalchemy.exc import IntegrityError

from domain.states import EventSeverity, EventSource
from persistence.base import Base
from persistence.db import create_db_engine, create_session_factory
from persistence.models import (
    Event,
    ExecutionAttempt,
    Principal,
    Project,
    Run,
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


def make_event(run_id: str, sequence: int, **overrides) -> Event:
    values = {
        "run_id": run_id,
        "sequence": sequence,
        "source": EventSource.RUN_COORDINATOR,
        "event_type": "RUN_STARTING",
        "category": "RUN",
        "severity": EventSeverity.INFO,
        "summary": "Run is starting.",
    }
    values.update(overrides)
    return Event(**values)


def test_event_round_trip(tmp_path):
    async def scenario():
        engine = await prepare(f"sqlite+aiosqlite:///{tmp_path / 'events.db'}")
        factory = create_session_factory(engine)
        try:
            async with factory() as session:
                run = await seed_run(session)
                session.add(make_event(run.id, 1, payload_json={"phase": "start"}))
                await session.commit()

            async with factory() as session:
                stored = (await session.execute(select(Event))).scalar_one()
                assert stored.sequence == 1
                assert stored.source is EventSource.RUN_COORDINATOR
                assert stored.severity is EventSeverity.INFO
                assert stored.payload_version == 1
                assert stored.payload_json == {"phase": "start"}
                assert stored.artifact_ids_json == []
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_run_sequence_is_unique(tmp_path):
    async def scenario():
        engine = await prepare(f"sqlite+aiosqlite:///{tmp_path / 'events.db'}")
        factory = create_session_factory(engine)
        try:
            async with factory() as session:
                run = await seed_run(session)
                session.add(make_event(run.id, 1))
                session.add(make_event(run.id, 1, event_type="RUN_STARTED"))
                with pytest.raises(IntegrityError):
                    await session.commit()
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_source_event_sequence_is_unique_per_attempt(tmp_path):
    async def scenario():
        engine = await prepare(f"sqlite+aiosqlite:///{tmp_path / 'events.db'}")
        factory = create_session_factory(engine)
        try:
            async with factory() as session:
                run = await seed_run(session)
                attempt = ExecutionAttempt(run_id=run.id, ordinal=1)
                session.add(attempt)
                await session.flush()
                session.add(
                    make_event(
                        run.id, 1, attempt_id=attempt.id, source_event_sequence=7
                    )
                )
                session.add(
                    make_event(
                        run.id, 2, attempt_id=attempt.id, source_event_sequence=7
                    )
                )
                with pytest.raises(IntegrityError):
                    await session.commit()
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_null_source_event_sequence_allows_duplicates(tmp_path):
    async def scenario():
        engine = await prepare(f"sqlite+aiosqlite:///{tmp_path / 'events.db'}")
        factory = create_session_factory(engine)
        try:
            async with factory() as session:
                run = await seed_run(session)
                attempt = ExecutionAttempt(run_id=run.id, ordinal=1)
                session.add(attempt)
                await session.flush()
                session.add(make_event(run.id, 1, attempt_id=attempt.id))
                session.add(make_event(run.id, 2, attempt_id=attempt.id))
                await session.commit()
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_invalid_severity_rejected(tmp_path):
    async def scenario():
        engine = await prepare(f"sqlite+aiosqlite:///{tmp_path / 'events.db'}")
        factory = create_session_factory(engine)
        try:
            async with factory() as session:
                run = await seed_run(session)
                with pytest.raises(IntegrityError):
                    await session.execute(
                        sql_text(
                            "INSERT INTO events (id, run_id, sequence, source, event_type, "
                            "category, severity, summary, payload_version, payload_json, "
                            "artifact_ids_json, occurred_at, recorded_at) "
                            "VALUES ('manual', :run_id, 9, 'RUN_COORDINATOR', 'X', 'RUN', "
                            "'NOPE', 'bad', 1, '{}', '[]', '2026-01-01', '2026-01-01')"
                        ),
                        {"run_id": run.id},
                    )
                    await session.commit()
        finally:
            await engine.dispose()

    asyncio.run(scenario())
