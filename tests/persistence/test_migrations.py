from pathlib import Path

from alembic import command
from alembic.config import Config

ROOT = Path(__file__).resolve().parents[2]
ALEMBIC_INI = ROOT / "alembic.ini"


def make_config() -> Config:
    return Config(str(ALEMBIC_INI))


def test_migrations_apply_and_downgrade_from_zero(tmp_path, monkeypatch):
    database_path = tmp_path / "migration.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{database_path}")

    config = make_config()
    command.upgrade(config, "head")

    assert database_path.exists()

    command.downgrade(config, "base")


def test_application_code_does_not_call_create_all():
    offenders = [
        str(path)
        for root in (ROOT / "apps", ROOT / "packages")
        for path in root.rglob("*.py")
        if "create_all" in path.read_text()
    ]

    assert offenders == []
