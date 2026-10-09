import asyncio
from pathlib import Path

from sqlalchemy import select

from coordinator.engines import build_engine_factory, register_pinned_installation
from coordinator.settings import CoordinatorSettings
from domain.states import CompatibilityStatus, EngineInstallationStatus
from persistence.base import Base
from persistence.db import create_db_engine, create_session_factory
from persistence.models import EngineInstallation

VENDOR_FACTORY = Path(__file__).resolve().parents[2] / "vendor/siesta/factory"
PINNED_REVISION = "20b149e0734b09730dfd22803d2695776fcf84b8"


def make_settings(tmp_path, **overrides) -> CoordinatorSettings:
    values = {
        "database_url": "sqlite+aiosqlite:///:memory:",
        "workspace_root": tmp_path / "workspaces",
        "engine_source_root": VENDOR_FACTORY,
        "development_mode": True,
        "_env_file": None,
    }
    values.update(overrides)
    return CoordinatorSettings(**values)


def test_engine_factory_is_unavailable_outside_development_mode(tmp_path):
    settings = make_settings(tmp_path, development_mode=False)

    assert build_engine_factory(settings) is None


def test_engine_factory_is_unavailable_without_installation_source(tmp_path):
    settings = make_settings(tmp_path, engine_source_root=tmp_path / "missing")

    assert build_engine_factory(settings) is None


def test_engine_factory_is_available_with_pinned_source(tmp_path):
    settings = make_settings(tmp_path)

    assert build_engine_factory(settings) is not None


def test_register_pinned_installation_is_idempotent(tmp_path):
    async def scenario():
        database_url = f"sqlite+aiosqlite:///{tmp_path / 'engines.db'}"
        engine = create_db_engine(database_url)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        factory = create_session_factory(engine)
        settings = make_settings(tmp_path)
        try:
            async with factory() as session:
                first = await register_pinned_installation(session, settings)
                await session.commit()
                first_id = first.id
                assert first.engine_family == "SIESTA"
                assert first.engine_revision == PINNED_REVISION
                assert first.status is EngineInstallationStatus.SUPPORTED
                assert first.compatibility_launch is CompatibilityStatus.SUPPORTED
                assert first.default_for_new_runs is True
                assert first.installation_digest.startswith("sha256:")
                assert first.capability_manifest_json["work_items"] is True

            async with factory() as session:
                second = await register_pinned_installation(session, settings)
                await session.commit()
                assert second.id == first_id
                stored = (
                    (await session.execute(select(EngineInstallation))).scalars().all()
                )
                assert len(stored) == 1
        finally:
            await engine.dispose()

    asyncio.run(scenario())
