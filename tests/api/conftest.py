from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from kallula_api.main import create_app
from kallula_api.settings import Settings


def build_client(database_url: str) -> TestClient:
    settings = Settings(database_url=database_url, log_level="WARNING", _env_file=None)
    return TestClient(create_app(settings))


@pytest.fixture
def client(tmp_path) -> Iterator[TestClient]:
    with build_client(f"sqlite+aiosqlite:///{tmp_path / 'test.db'}") as test_client:
        yield test_client


@pytest.fixture
def unavailable_client() -> Iterator[TestClient]:
    with build_client(
        "sqlite+aiosqlite:////nonexistent-kallula/test.db"
    ) as test_client:
        yield test_client
