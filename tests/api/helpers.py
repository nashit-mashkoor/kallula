import asyncio

from fastapi.testclient import TestClient
from sqlalchemy import select

from api.main import create_app
from api.settings import Settings
from persistence.base import Base
from persistence.db import create_db_engine, create_session_factory
from persistence.models import Command, Event, Principal


async def _prepare_database(database_url: str) -> None:
    engine = create_db_engine(database_url)
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
    finally:
        await engine.dispose()


def prepare_database(database_url: str) -> None:
    asyncio.run(_prepare_database(database_url))


def build_client(database_url: str, **overrides) -> TestClient:
    settings = Settings(
        database_url=database_url, log_level="WARNING", _env_file=None, **overrides
    )
    return TestClient(create_app(settings))


async def _seed_command(database_url: str) -> str:
    engine = create_db_engine(database_url)
    factory = create_session_factory(engine)
    try:
        async with factory() as session:
            principal = Principal(
                id="dev-principal",
                auth_provider="development",
                auth_subject="dev-principal",
                display_name="Development User",
            )
            session.add(principal)
            command = Command(
                actor_principal_id=principal.id,
                command_type="START_RUN",
                target_type="RUN",
                target_id="run-1",
                request_json={},
                request_hash="hash",
                idempotency_key="key",
            )
            session.add(command)
            await session.commit()
            return command.id
    finally:
        await engine.dispose()


def seed_command(database_url: str) -> str:
    return asyncio.run(_seed_command(database_url))


async def _fetch_events(database_url: str, run_id: str) -> list[tuple[str, int, str]]:
    engine = create_db_engine(database_url)
    factory = create_session_factory(engine)
    try:
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
            return [
                (event.event_type, event.sequence, event.source.value)
                for event in events
            ]
    finally:
        await engine.dispose()


def fetch_events(database_url: str, run_id: str) -> list[tuple[str, int, str]]:
    return asyncio.run(_fetch_events(database_url, run_id))
