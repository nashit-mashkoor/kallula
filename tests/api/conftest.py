import asyncio
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from api.main import create_app
from api.settings import Settings
from persistence.base import Base
from persistence.db import create_db_engine


async def prepare_database(database_url: str) -> None:
    engine = create_db_engine(database_url)
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
    finally:
        await engine.dispose()


def build_client(database_url: str, **overrides) -> TestClient:
    settings = Settings(
        database_url=database_url, log_level="WARNING", _env_file=None, **overrides
    )
    return TestClient(create_app(settings))


@pytest.fixture
def database_url(tmp_path) -> str:
    url = f"sqlite+aiosqlite:///{tmp_path / 'test.db'}"
    asyncio.run(prepare_database(url))
    return url


@pytest.fixture
def client(database_url) -> Iterator[TestClient]:
    with build_client(database_url) as test_client:
        yield test_client


@pytest.fixture
def unavailable_client() -> Iterator[TestClient]:
    with build_client(
        "sqlite+aiosqlite:////nonexistent-kallula/test.db"
    ) as test_client:
        yield test_client
