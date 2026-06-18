"""Action catalog and state snapshot for the assistant.

The assistant never executes anything. It *proposes* one of these actions; the
user confirms in the UI; the frontend then runs it through the same role-gated
REST endpoint with the user's own token. This module is the single source of
truth for what may be proposed: it validates the arguments a model produced,
resolves friendly references (a VLAN *name*, a profile *name*) to the ids the
API needs, and builds the exact request the frontend should send. Because the
request is constructed here from the catalog (never from raw model output), a
manipulated model cannot reach an arbitrary endpoint.
"""

from __future__ import annotations

import datetime as dt
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.agent import Agent
from ..models.asset import VLAN, Asset, Criticality, DataSensitivity
from ..models.change import ChangeEvent
from ..models.scan import ComplianceFramework, ScanProfile, ScanRun, ScanType
from ..models.task import Task
from ..models.user import User

WRITE_ROLES: tuple[str, ...] = ("admin", "operator")
ADMIN_ROLES: tuple[str, ...] = ("admin",)

_CRITICALITIES = [c.value for c in Criticality]
_SENSITIVITIES = [d.value for d in DataSensitivity]
_SCAN_TYPES = [s.value for s in ScanType]
_FRAMEWORKS = [f.value for f in ComplianceFramework]

_ONLINE_WINDOW = dt.timedelta(minutes=2)


class ActionError(Exception):
    """A proposed action's arguments are invalid or a reference is unknown.

    The message is safe to show the user (e.g. "VLAN 'DMZ' not found.")."""


# --- arg helpers -----------------------------------------------------------


def _req_str(args: dict[str, Any], key: str) -> str:
    value = args.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ActionError(f"'{key}' is required.")
    return value.strip()


def _opt_str(args: dict[str, Any], key: str) -> str | None:
    value = args.get(key)
    return value.strip() if isinstance(value, str) and value.strip() else None


def _opt_int(args: dict[str, Any], key: str) -> int | None:
    value = args.get(key)
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ActionError(f"'{key}' must be a number.") from exc


def _enum(
    args: dict[str, Any], key: str, allowed: list[str], default: str | None
) -> str | None:
    value = args.get(key)
    if value is None or value == "":
        return default
    value = str(value).strip().lower()
    if value not in allowed:
        raise ActionError(f"'{key}' must be one of: {', '.join(allowed)}.")
    return value


def _bool(args: dict[str, Any], key: str, default: bool) -> bool:
    value = args.get(key)
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ("1", "true", "yes", "on")


async def _vlan_id_by_name(session: AsyncSession, name: str) -> str:
    row = (
        await session.execute(select(VLAN).where(func.lower(VLAN.name) == name.lower()))
    ).scalar_one_or_none()
    if row is None:
        raise ActionError(f"VLAN '{name}' not found.")
    return str(row.id)


async def _user_id_by_email(session: AsyncSession, email: str) -> str:
    row = (
        await session.execute(
            select(User).where(func.lower(User.email) == email.lower())
        )
    ).scalar_one_or_none()
    if row is None:
        raise ActionError(f"User '{email}' not found.")
    return str(row.id)


# A built action: a friendly summary (for the confirm card) plus the exact
# request the frontend will send.
BuiltAction = tuple[dict[str, Any], dict[str, Any]]


async def _vlan_create(session: AsyncSession, args: dict[str, Any]) -> BuiltAction:
    name = _req_str(args, "name")
    tag = _opt_int(args, "vlan_tag")
    desc = _opt_str(args, "description")
    summary = {"name": name, "vlan_tag": tag, "description": desc}
    body = {"name": name, "vlan_tag": tag, "description": desc}
    return summary, {"method": "POST", "path": "/vlans", "body": body}


async def _iprange_create(session: AsyncSession, args: dict[str, Any]) -> BuiltAction:
    cidr = _req_str(args, "cidr")
    desc = _opt_str(args, "description")
    vlan_name = _opt_str(args, "vlan_name")
    vlan_id = await _vlan_id_by_name(session, vlan_name) if vlan_name else None
    summary = {"cidr": cidr, "vlan": vlan_name, "description": desc}
    body = {"cidr": cidr, "vlan_id": vlan_id, "description": desc}
    return summary, {"method": "POST", "path": "/ip-ranges", "body": body}


async def _asset_create(session: AsyncSession, args: dict[str, Any]) -> BuiltAction:
    ip = _req_str(args, "ip")
    hostname = _opt_str(args, "hostname")
    criticality = _enum(args, "criticality", _CRITICALITIES, "medium")
    sensitivity = _enum(args, "data_sensitivity", _SENSITIVITIES, "none")
    vlan_name = _opt_str(args, "vlan_name")
    owner_email = _opt_str(args, "owner_email")
    vlan_id = await _vlan_id_by_name(session, vlan_name) if vlan_name else None
    owner_id = await _user_id_by_email(session, owner_email) if owner_email else None
    summary = {
        "ip": ip,
        "hostname": hostname,
        "vlan": vlan_name,
        "owner": owner_email,
        "criticality": criticality,
        "data_sensitivity": sensitivity,
    }
    body = {
        "ip": ip,
        "hostname": hostname,
        "vlan_id": vlan_id,
        "owner_id": owner_id,
        "criticality": criticality,
        "data_sensitivity": sensitivity,
    }
    return summary, {"method": "POST", "path": "/assets", "body": body}


async def _scanprofile_create(session: AsyncSession, args: dict[str, Any]) -> BuiltAction:
    name = _req_str(args, "name")
    raw_targets = args.get("targets")
    if isinstance(raw_targets, str):
        raw_targets = re.split(r"[\s,]+", raw_targets)
    if not isinstance(raw_targets, list):
        raise ActionError("'targets' is required (a list of IPs or CIDRs).")
    targets = [str(t).strip() for t in raw_targets if str(t).strip()]
    if not targets:
        raise ActionError("'targets' is required (a list of IPs or CIDRs).")
    ports = _opt_str(args, "ports") or "top-1000"
    scan_type = _enum(args, "scan_type", _SCAN_TYPES, "connect")
    segment = _opt_str(args, "segment")
    framework = _enum(args, "compliance_framework", _FRAMEWORKS, None)
    cron = _opt_str(args, "cron")
    service_detection = _bool(args, "service_detection", True)
    summary = {
        "name": name,
        "targets": ", ".join(targets),
        "ports": ports,
        "scan_type": scan_type,
        "segment": segment,
        "compliance_framework": framework,
        "cron": cron,
    }
    body = {
        "name": name,
        "targets": targets,
        "ports": ports,
        "scan_type": scan_type,
        "service_detection": service_detection,
        "segment": segment,
        "compliance_framework": framework,
        "cron": cron,
    }
    return summary, {"method": "POST", "path": "/scan-profiles", "body": body}


async def _scan_run(session: AsyncSession, args: dict[str, Any]) -> BuiltAction:
    name = _req_str(args, "profile_name")
    profile = (
        await session.execute(
            select(ScanProfile).where(func.lower(ScanProfile.name) == name.lower())
        )
    ).scalar_one_or_none()
    if profile is None:
        raise ActionError(f"Scan profile '{name}' not found.")
    return (
        {"profile_name": profile.name},
        {"method": "POST", "path": f"/scan-profiles/{profile.id}/run", "body": None},
    )


async def _agent_enroll(session: AsyncSession, args: dict[str, Any]) -> BuiltAction:
    name = _req_str(args, "name")
    segment = _opt_str(args, "segment")
    summary = {"name": name, "segment": segment}
    body = {"name": name, "segment": segment}
    return summary, {"method": "POST", "path": "/agents", "body": body}


@dataclass(frozen=True)
class ActionSpec:
    name: str
    roles: tuple[str, ...]
    description: str
    params: str  # human-readable param description for the prompt
    build: Callable[[AsyncSession, dict[str, Any]], Awaitable[BuiltAction]]


CATALOG: list[ActionSpec] = [
    ActionSpec(
        "vlan.create",
        WRITE_ROLES,
        "Create a VLAN (network segment).",
        "name (required), vlan_tag (number, optional), description (optional)",
        _vlan_create,
    ),
    ActionSpec(
        "iprange.create",
        WRITE_ROLES,
        "Create an IP range (CIDR block).",
        "cidr (required), vlan_name (optional), description (optional)",
        _iprange_create,
    ),
    ActionSpec(
        "asset.create",
        WRITE_ROLES,
        "Add an asset (a host to scan).",
        "ip (required), hostname (optional), vlan_name (optional), owner_email "
        "(optional), criticality (low|medium|high|critical), data_sensitivity "
        "(none|pii|cde|ephi)",
        _asset_create,
    ),
    ActionSpec(
        "scanprofile.create",
        WRITE_ROLES,
        "Create a scan profile.",
        "name (required), targets (required, list of IPs/CIDRs), ports (optional, "
        "default top-1000), scan_type (connect|syn|udp), segment (optional), "
        "compliance_framework (pci|hipaa|soc2|iso27001|nist, optional), cron "
        "(optional), service_detection (true|false, default true)",
        _scanprofile_create,
    ),
    ActionSpec(
        "scan.run",
        WRITE_ROLES,
        "Run an existing scan profile now.",
        "profile_name (required)",
        _scan_run,
    ),
    ActionSpec(
        "agent.enroll",
        ADMIN_ROLES,
        "Enroll a scan agent (returns a one-time token).",
        "name (required), segment (optional)",
        _agent_enroll,
    ),
]

CATALOG_BY_NAME: dict[str, ActionSpec] = {a.name: a for a in CATALOG}


def actions_for_role(role: str) -> list[ActionSpec]:
    """The subset of the catalog a given role is allowed to propose."""
    return [a for a in CATALOG if role in a.roles]


def _is_online(last_seen: dt.datetime | None, now: dt.datetime) -> bool:
    if last_seen is None:
        return False
    if last_seen.tzinfo is None:  # SQLite drops tzinfo; stored values are UTC
        last_seen = last_seen.replace(tzinfo=dt.timezone.utc)
    return (now - last_seen) < _ONLINE_WINDOW


async def build_snapshot(session: AsyncSession) -> str:
    """A compact, current view of the deployment for the model to ground
    answers on. Counts and names only; no secrets."""

    async def count(model, *where) -> int:
        query = select(func.count()).select_from(model)
        for clause in where:
            query = query.where(clause)
        return (await session.execute(query)).scalar_one()

    n_assets = await count(Asset)
    vlan_names = (
        await session.execute(select(VLAN.name).order_by(VLAN.name).limit(20))
    ).scalars().all()
    profile_names = (
        await session.execute(select(ScanProfile.name).order_by(ScanProfile.name).limit(20))
    ).scalars().all()
    agent_rows = (
        await session.execute(select(Agent.name, Agent.enabled, Agent.last_seen_at))
    ).all()
    open_changes = await count(ChangeEvent, ChangeEvent.status == "open")
    open_tasks = await count(Task, Task.status.in_(["open", "in_progress"]))
    pending_runs = await count(ScanRun, ScanRun.status == "pending")

    now = dt.datetime.now(tz=dt.timezone.utc)
    agent_labels = [
        f"{name} ({'online' if _is_online(ls, now) else 'offline' if enabled else 'disabled'})"
        for name, enabled, ls in agent_rows
    ]
    return "\n".join(
        [
            f"Assets: {n_assets}",
            f"VLANs ({len(vlan_names)}): {', '.join(vlan_names) or 'none'}",
            f"Scan profiles ({len(profile_names)}): {', '.join(profile_names) or 'none'}",
            f"Agents ({len(agent_labels)}): {', '.join(agent_labels) or 'none'}",
            f"Open changes: {open_changes}",
            f"Open tasks: {open_tasks}",
            f"Pending scan runs: {pending_runs}",
        ]
    )
