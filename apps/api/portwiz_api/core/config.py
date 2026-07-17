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
    # Running version, injected at image build from the release tag (PORTWIZ_VERSION).
    # Empty falls back to the packaged __version__; drives the update check.
    app_version: str = ""

    # Update check: poll GitHub Releases for a newer version. On by default but
    # disable-able for air-gapped/compliance installs (it contacts an external
    # service). The repo is configurable for forks.
    update_check_enabled: bool = True
    update_repo: str = "keraattin/PortWiz"
    # One-click "update now": the API only records a request; a separate updater
    # sidecar (which holds the Docker socket) applies it. Off unless that sidecar
    # is deployed, so the API never gets Docker access.
    update_apply_enabled: bool = False

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

    # Trust the X-Forwarded-For header for the client IP (agent last_ip). Enable
    # ONLY when the API sits behind a trusted reverse proxy that sets it (the
    # production single-origin nginx does); otherwise a direct client could spoof
    # it. Off by default so a directly-exposed API can't be fooled.
    trust_forwarded_for: bool = False

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

    # Defaults pre-filled when creating a new scan profile (a field the request
    # omits falls back to these).
    default_scan_ports: str = "top-1000"
    default_scan_type: str = "connect"
    default_service_detection: bool = True
    default_scan_rate_limit_pps: int = 1000

    # Data retention: prune raw observations older than this many days (0 = keep
    # forever). Only the high-volume time-series is pruned; scan runs, change
    # events and the immutable audit log are always retained.
    retention_observation_days: int = 0

    # --- AI layer (provider-agnostic) ---
    # Selected provider id (see PROVIDER_REGISTRY): "none" | "ollama" | "claude" |
    # "openai" | "gemini" | "mistral" | "groq" | "openrouter" | "deepseek" | "custom".
    ai_provider: str = "ollama"
    ollama_base_url: str = "http://ollama:11434"
    # A small-but-capable default: reliable enough for the assistant's structured
    # actions and fingerprint enrichment, and a ~2GB pull rather than tens of GB.
    # Sub-1B models (e.g. qwen2.5:0.5b) are too weak for the assistant.
    ollama_model: str = "qwen2.5:3b"
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

    # Chat webhooks (Slack / Microsoft Teams). Each fires on confirmed changes,
    # independently of email, when enabled and its incoming-webhook URL is set.
    slack_enabled: bool = False
    slack_webhook_url: str | None = None
    teams_enabled: bool = False
    teams_webhook_url: str | None = None

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
    # Optional Jira priority name to set per PortWiz severity (blank = leave the
    # priority unset so the project default applies).
    jira_priority_high: str = ""
    jira_priority_medium: str = ""
    jira_priority_low: str = ""
    # Advanced: extra Jira fields merged verbatim into every created issue, as a
    # JSON object of field id -> value (e.g. required custom fields). A blank or
    # invalid value is ignored.
    jira_extra_fields: str = ""

    # CVE enrichment: look up known vulnerabilities for discovered service+version.
    # Disabled unless enabled. Data is authoritative from the source (never
    # invented); the AI layer only summarises what a source returns.
    cve_enabled: bool = False
    cve_source: str = "nvd"  # nvd (offline/other sources plug in behind CVESource later)
    cve_api_url: str = ""  # blank = the source's default endpoint
    cve_api_key: str | None = None  # NVD API key raises the rate limit (optional)
    cve_min_cvss: float = 0.0  # ignore findings below this CVSS base score
    cve_recheck_hours: int = 0  # 0 = manual only; >0 auto re-checks on this cadence

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


# Substrings that mark a value as an unfilled placeholder from the env examples.
_PLACEHOLDER_MARKERS = ("change-me", "dev-insecure")


def check_production_secrets(settings: Settings) -> None:
    """Refuse to run production with unset or placeholder security secrets.

    In non-production environments this is a no-op (the dev defaults are fine for
    localhost). In production, a missing or still-placeholder ``secret_key`` or
    ``encryption_key`` is a hard startup error rather than a silent fail-open to
    weak signing / plaintext-at-rest.
    """
    if settings.environment != "production":
        return

    def _placeholder(value: str | None) -> bool:
        return not value or any(m in value.lower() for m in _PLACEHOLDER_MARKERS)

    missing = [
        name
        for name, value in (
            ("PORTWIZ_SECRET_KEY", settings.secret_key),
            ("PORTWIZ_ENCRYPTION_KEY", settings.encryption_key),
        )
        if _placeholder(value)
    ]
    if missing:
        raise RuntimeError(
            "Refusing to start in production with a missing or placeholder "
            + " and ".join(missing)
            + ". Generate real values (e.g. `openssl rand -hex 32` and a Fernet key)."
        )
