"""Application configuration, loaded from environment variables.

All settings are read with the ``PORTWIZ_`` prefix, e.g. ``PORTWIZ_SECRET_KEY``.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="PORTWIZ_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- General ---
    app_name: str = "PortWiz"
    environment: str = "development"
    debug: bool = True
    api_v1_prefix: str = "/api/v1"

    # --- Database ---
    # Async SQLAlchemy URL (asyncpg driver).
    database_url: str = "postgresql+asyncpg://portwiz:portwiz@db:5432/portwiz"

    # --- Auth ---
    # MUST be overridden in production via PORTWIZ_SECRET_KEY.
    secret_key: str = "dev-insecure-change-me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    # First admin user seeded on startup when no users exist.
    first_admin_email: str | None = None
    first_admin_password: str | None = None
    first_admin_full_name: str = "PortWiz Administrator"

    # --- CORS ---
    cors_origins: list[str] = ["http://localhost:5173"]

    # --- Task queue (Celery + Valkey/Redis) ---
    celery_broker_url: str = "redis://valkey:6379/0"
    celery_result_backend: str = "redis://valkey:6379/1"

    # --- AI layer (provider-agnostic) ---
    # Provider for fingerprint enrichment and the assistant: "ollama" | "claude" | "none".
    ai_provider: str = "ollama"
    ollama_base_url: str = "http://ollama:11434"
    ollama_model: str = "llama3.3"
    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-sonnet-4-6"


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()
