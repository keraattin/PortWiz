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
    jira_url: str | None
    jira_project_key: str
    jira_configured: bool

    # NetBox (IPAM)
    netbox_enabled: bool
    netbox_url: str | None
    netbox_configured: bool


class TestResult(BaseModel):
    ok: bool
    detail: str


class EmailTestRequest(BaseModel):
    recipient: str | None = None
