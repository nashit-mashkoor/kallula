from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = "sqlite+aiosqlite:///./kallula.db"
    development_mode: bool = True
    auth_mode: str = "development"
    dev_principal_id: str = "dev-principal"
    dev_principal_display_name: str = "Development User"
    dev_principal_email: str = "dev@kallula.local"
    workspace_root: Path = Path("var/workspaces")
    engine_installation_root: Path = Path("var/engines")
    runtime_manager_backend: str = "local"
    preview_gateway_base_url: str = "http://localhost:8080"
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
