from pathlib import Path

from coordinator.engines import build_engine_factory
from coordinator.settings import CoordinatorSettings

VENDOR_FACTORY = Path(__file__).resolve().parents[2] / "vendor/siesta/factory"


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
