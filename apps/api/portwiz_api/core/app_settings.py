"""Runtime-editable configuration: environment defaults overlaid with DB rows.

The environment provides defaults (via :class:`Settings`); admins can override
individual values from the UI, stored in the ``app_settings`` table. Reading
effective config means env values with overrides applied. Secret values live in
this table and are never returned to clients.
"""

from __future__ import annotations

import datetime as dt
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.app_setting import AppSetting
from .audit import append_audit
from .config import Settings, get_settings
from .crypto import decrypt_secret, encrypt_secret

# Settings fields an admin may override from the UI.
EDITABLE_KEYS: list[str] = [
    # AI
    "ai_provider",
    "ollama_base_url",
    "ollama_model",
    "anthropic_api_key",
    "anthropic_model",
    "compat_base_url",
    "compat_model",
    "compat_api_key",
    # Email (SMTP)
    "notifications_enabled",
    "smtp_host",
    "smtp_port",
    "smtp_from",
    "smtp_username",
    "smtp_password",
    "smtp_use_tls",
    "notification_recipients",
    # Jira
    "jira_enabled",
    "jira_deployment",
    "jira_url",
    "jira_email",
    "jira_api_token",
    "jira_project_key",
    "jira_issue_type",
    "jira_default_assignee",
    "jira_labels",
    # NetBox
    "netbox_enabled",
    "netbox_url",
    "netbox_token",
    "netbox_writeback_enabled",
    # Operational (system)
    "change_confirmations",
]

# Keys whose values must never be returned to clients and are only updated when a
# non-empty replacement is supplied.
SECRET_KEYS: frozenset[str] = frozenset(
    {"anthropic_api_key", "compat_api_key", "smtp_password", "jira_api_token", "netbox_token"}
)


def _to_str(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, list):
        return ",".join(str(v) for v in value)
    return "" if value is None else str(value)


def _cast(current: Any, raw: str) -> Any:
    """Cast a stored string back to the field's type, inferred from the default."""
    if isinstance(current, bool):
        return raw.strip().lower() in ("1", "true", "yes", "on")
    if isinstance(current, int) and not isinstance(current, bool):
        return int(raw) if raw.strip() else 0
    if isinstance(current, list):
        return [x.strip() for x in raw.split(",") if x.strip()]
    return raw


async def load_overrides(session: AsyncSession) -> dict[str, str]:
    rows = (await session.execute(select(AppSetting))).scalars().all()
    return {r.key: r.value for r in rows if r.value is not None}


async def effective_settings(session: AsyncSession) -> Settings:
    """Environment defaults with DB overrides applied. Stored secrets are
    decrypted on the way out (legacy plaintext passes through unchanged)."""
    base = get_settings()
    overrides = await load_overrides(session)
    if not overrides:
        return base
    data = base.model_dump()
    for key, raw in overrides.items():
        if key in data:
            if key in SECRET_KEYS:
                raw = decrypt_secret(raw, base.encryption_key)
            data[key] = _cast(data[key], raw)
    return Settings(**data)


async def set_overrides(
    session: AsyncSession,
    updates: dict[str, Any],
    *,
    actor_id: uuid.UUID | None,
    actor_email: str | None,
) -> list[str]:
    """Upsert override rows. Blank secret values are ignored (keep current).
    The caller's audit records which keys changed, never their values."""
    now = dt.datetime.now(tz=dt.timezone.utc)
    enc_key = get_settings().encryption_key
    changed: list[str] = []
    for key, value in updates.items():
        if key not in EDITABLE_KEYS:
            continue
        if key in SECRET_KEYS and (value is None or value == ""):
            continue
        row = await session.get(AppSetting, key)
        stored = _to_str(value)
        if key in SECRET_KEYS:
            stored = encrypt_secret(stored, enc_key)
        if row is None:
            session.add(
                AppSetting(key=key, value=stored, updated_at=now, updated_by=actor_id)
            )
        else:
            row.value = stored
            row.updated_at = now
            row.updated_by = actor_id
        changed.append(key)

    if changed:
        await append_audit(
            session,
            action="settings.updated",
            actor_id=actor_id,
            actor_email=actor_email,
            target_type="settings",
            target_id=None,
            payload={"changed": sorted(changed)},
        )
        await session.commit()
    return changed
