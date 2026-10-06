import asyncio

import pytest

from coordinator.main import start
from persistence.db import DatabaseUnavailableError


def test_coordinator_connects_to_database(tmp_path):
    engine = asyncio.run(start(f"sqlite+aiosqlite:///{tmp_path / 'coordinator.db'}"))
    try:
        assert engine is not None
    finally:
        asyncio.run(engine.dispose())


def test_coordinator_fails_on_unreachable_database():
    with pytest.raises(DatabaseUnavailableError):
        asyncio.run(start("sqlite+aiosqlite:////nonexistent-coordinator/test.db"))
