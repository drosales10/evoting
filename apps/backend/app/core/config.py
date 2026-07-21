from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

WORKSPACE_ROOT = Path(__file__).resolve().parents[4]


class Settings(BaseSettings):
    app_name: str = "eVoting API"
    environment: str = "development"
    database_url: str | None = None
    cors_origins: list[str] = ["http://localhost:3000"]
    jwt_secret: str | None = None
    access_token_minutes: int = 10
    refresh_token_days: int = 7
    secure_cookies: bool = False

    model_config = SettingsConfigDict(
        env_file=(WORKSPACE_ROOT / ".env", WORKSPACE_ROOT / "apps/backend/.env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
