from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from helpers import build_client, prepare_database


@pytest.fixture
def database_url(tmp_path) -> str:
    url = f"sqlite+aiosqlite:///{tmp_path / 'test.db'}"
    prepare_database(url)
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
