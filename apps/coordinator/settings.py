from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class CoordinatorSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = "sqlite+aiosqlite:///./kallula.db"
    development_mode: bool = True
    workspace_root: Path = Path("var/workspaces")
    engine_source_root: Path = Path("vendor/siesta/factory")
    engine_poll_interval_seconds: float = 0.5
    log_level: str = "INFO"
