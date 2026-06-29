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

    # At-rest encryption of stored secrets (API keys, tokens, SMTP password).
    # A urlsafe-base64 Fernet key, separate from secret_key; generate with:
    #   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    # When unset, secrets are stored as plaintext (a startup warning is logged).
    encryption_key: str | None = None

    # First admin user seeded on startup when no users exist.
    first_admin_email: str | None = None
    first_admin_password: str | None = None
    first_admin_full_name: str = "PortWiz Administrator"

    # --- CORS ---
    cors_origins: list[str] = ["http://localhost:5173"]

    # --- Task queue (Celery + Valkey/Redis) ---
    celery_broker_url: str = "redis://valkey:6379/0"
    celery_result_backend: str = "redis://valkey:6379/1"

    # Scan reliability: a run an agent claimed but did not finish within
    # scan_stale_minutes is requeued, up to scan_max_attempts before it fails.
    scan_stale_minutes: int = 30
    scan_max_attempts: int = 3

    # Change detection: a new per-port state must persist for this many
    # consecutive completed runs before it is confirmed (flapping noise filter).
    change_confirmations: int = 2

    # Agent health/protocol. An agent is "online" if it heartbeat within
    # agent_online_seconds; agent_poll_seconds is the recommended poll interval
    # surfaced in the deploy instructions.
    agent_online_seconds: int = 120
    agent_poll_seconds: int = 15

    # --- AI layer (provider-agnostic) ---
    # Selected provider id (see PROVIDER_REGISTRY): "none" | "ollama" | "claude" |
    # "openai" | "gemini" | "mistral" | "groq" | "openrouter" | "deepseek" | "custom".
    ai_provider: str = "ollama"
    ollama_base_url: str = "http://ollama:11434"
    ollama_model: str = "llama3.3"
    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-sonnet-4-6"
    # Shared config for every OpenAI-compatible provider (one is active at a time).
    # Blank base_url/model fall back to the selected provider's registry default.
    compat_base_url: str = ""
    compat_model: str = ""
    compat_api_key: str | None = None

    # Notifications (email). No emails are sent unless recipients are configured.
    notifications_enabled: bool = True
    smtp_host: str = "mailhog"
    smtp_port: int = 1025
    smtp_from: str = "portwiz@portwiz.local"
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_use_tls: bool = False
    notification_recipients: list[str] = []

    # Jira integration (issue tracker). Disabled unless fully configured.
    jira_enabled: bool = False
    jira_deployment: str = "cloud"  # cloud | server (Server/Data Center, on-prem)
    jira_url: str | None = None  # e.g. https://yourorg.atlassian.net
    jira_email: str | None = None  # cloud only; basic auth identity
    jira_api_token: str | None = None  # cloud API token, or server Personal Access Token
    jira_project_key: str = "PORT"
    jira_issue_type: str = "Task"
    jira_default_assignee: str | None = None  # accountId (cloud) or username (server)
    jira_labels: str = ""  # comma-separated labels added to every created issue

    # NetBox (IPAM) inventory source. Disabled unless fully configured.
    netbox_enabled: bool = False
    netbox_url: str | None = None  # e.g. https://netbox.example.com
    netbox_token: str | None = None
    # When set, each scan automatically writes its discovered hosts back to
    # NetBox. Off by default; the manual push button is the primary path.
    netbox_writeback_enabled: bool = False


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()
