"""Schemas for the settings / integration-status surface.

Only non-secret configuration is exposed (provider names, hosts, ports,
booleans). API keys, SMTP passwords, and Jira tokens are never serialized.
"""

from __future__ import annotations

from pydantic import BaseModel


class SettingsStatus(BaseModel):
    app_name: str
    environment: str
    version: str

    # AI
    ai_provider: str  # ollama | claude | none
    ai_model: str
    ai_configured: bool

    # Email (SMTP)
    email_enabled: bool
    smtp_host: str
    smtp_port: int
    smtp_from: str
    email_recipients: list[str]

    # Jira
    jira_enabled: bool
    jira_deployment: str
    jira_url: str | None
    jira_project_key: str
    jira_configured: bool

    # NetBox (IPAM)
    netbox_enabled: bool
    netbox_url: str | None
    netbox_configured: bool

    # Operational (read-only, for clients: agent health windows + scan defaults)
    agent_online_seconds: int
    agent_poll_seconds: int
    default_scan_ports: str
    default_scan_type: str
    default_service_detection: bool


class AiProviderInfo(BaseModel):
    """Metadata for one selectable AI provider, used to render the settings UI."""

    id: str
    label: str
    kind: str
    default_base_url: str
    default_model: str
    needs_api_key: bool
    needs_base_url: bool
    console_url: str


class TestResult(BaseModel):
    ok: bool
    detail: str


class JiraProject(BaseModel):
    key: str
    name: str


class JiraUser(BaseModel):
    id: str  # accountId (Cloud) or username (Server/DC)
    label: str


class EmailTestRequest(BaseModel):
    recipient: str | None = None


class SettingsConfig(BaseModel):
    """Editable configuration. Secret values are never included; a `*_set`
    boolean reports whether each secret currently has a value."""

    ai_provider: str
    ollama_base_url: str
    ollama_model: str
    anthropic_model: str
    anthropic_api_key_set: bool
    compat_base_url: str
    compat_model: str
    compat_api_key_set: bool

    notifications_enabled: bool
    smtp_host: str
    smtp_port: int
    smtp_from: str
    smtp_username: str | None
    smtp_use_tls: bool
    smtp_password_set: bool
    notification_recipients: list[str]

    jira_enabled: bool
    jira_deployment: str
    jira_url: str | None
    jira_email: str | None
    jira_project_key: str
    jira_issue_type: str
    jira_default_assignee: str | None
    jira_labels: str
    jira_api_token_set: bool

    netbox_enabled: bool
    netbox_url: str | None
    netbox_writeback_enabled: bool
    netbox_token_set: bool

    change_confirmations: int
    agent_online_seconds: int
    agent_poll_seconds: int
    scan_stale_minutes: int
    scan_max_attempts: int
    default_scan_ports: str
    default_scan_type: str
    default_service_detection: bool
    default_scan_rate_limit_pps: int
    retention_observation_days: int


class SettingsConfigUpdate(BaseModel):
    """PATCH payload. Only provided fields change; a blank secret is ignored."""

    ai_provider: str | None = None
    ollama_base_url: str | None = None
    ollama_model: str | None = None
    anthropic_api_key: str | None = None
    anthropic_model: str | None = None
    compat_base_url: str | None = None
    compat_model: str | None = None
    compat_api_key: str | None = None

    notifications_enabled: bool | None = None
    smtp_host: str | None = None
    smtp_port: int | None = None
    smtp_from: str | None = None
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_use_tls: bool | None = None
    notification_recipients: list[str] | None = None

    jira_enabled: bool | None = None
    jira_deployment: str | None = None
    jira_url: str | None = None
    jira_email: str | None = None
    jira_api_token: str | None = None
    jira_project_key: str | None = None
    jira_issue_type: str | None = None
    jira_default_assignee: str | None = None
    jira_labels: str | None = None

    netbox_enabled: bool | None = None
    netbox_url: str | None = None
    netbox_token: str | None = None
    netbox_writeback_enabled: bool | None = None

    change_confirmations: int | None = None
    agent_online_seconds: int | None = None
    agent_poll_seconds: int | None = None
    scan_stale_minutes: int | None = None
    scan_max_attempts: int | None = None
    default_scan_ports: str | None = None
    default_scan_type: str | None = None
    default_service_detection: bool | None = None
    default_scan_rate_limit_pps: int | None = None
    retention_observation_days: int | None = None
