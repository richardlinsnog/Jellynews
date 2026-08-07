
from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # App
    APP_ENV: str = "production"
    APP_SECRET_KEY: str = ""  # Required — app refuses to start if empty
    DEBUG: bool = False
    PORT: int = 8000
    TZ: str = "America/Sao_Paulo"
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"

    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./data/jellynews.db"

    # Security
    JWT_EXPIRATION_MINUTES: int = 60
    JWT_REFRESH_EXPIRATION_DAYS: int = 7
    RATE_LIMIT_LOGIN: str = "5/minute"
    SECRETS_ENCRYPTION_KEY: str = ""
    ALLOW_UNVERIFIED_TEMPLATES: bool = False

    # Setup
    FIRST_RUN_SETUP: bool = True

    # Observability
    HEALTHCHECK_ENABLED: bool = True

    @property
    def is_development(self) -> bool:
        return self.APP_ENV == "development"

    @property
    def db_path(self) -> Path:
        """Absolute path to the SQLite database file."""
        return Path(self.DATABASE_URL.replace("sqlite:///", "")).resolve()

    @property
    def secrets_encryption_key(self) -> str:
        if self.SECRETS_ENCRYPTION_KEY:
            return self.SECRETS_ENCRYPTION_KEY
        # Derive from APP_SECRET_KEY via PBKDF2 — will be handled by SecretsVaultService
        return ""


def get_settings() -> Settings:
    return Settings()


settings = get_settings()

