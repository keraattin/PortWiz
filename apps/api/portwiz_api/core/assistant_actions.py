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
import ipaddress
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.agent import Agent
from ..models.asset import VLAN, Asset, Criticality, DataSensitivity, IPRange
from ..models.change import ChangeEvent
from ..models.scan import ComplianceFramework, ScanProfile, ScanRun, ScanType
from ..models.task import Task, TaskStatus
from ..models.user import User

WRITE_ROLES: tuple[str, ...] = ("admin", "operator")
ADMIN_ROLES: tuple[str, ...] = ("admin",)

_CRITICALITIES = [c.value for c in Criticality]
_SENSITIVITIES = [d.value for d in DataSensitivity]
_SCAN_TYPES = [s.value for s in ScanType]
_FRAMEWORKS = [f.value for f in ComplianceFramework]
_TASK_STATUSES = [s.value for s in TaskStatus]

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


async def _vlan_bulk_create(session: AsyncSession, args: dict[str, Any]) -> BuiltAction:
    items = args.get("items")
    if not isinstance(items, list) or not items:
        raise ActionError("Provide a non-empty 'items' list of VLANs to create.")
    built: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            raise ActionError("Each item must be an object with at least a name.")
        name = item.get("name")
        if not isinstance(name, str) or not name.strip():
            raise ActionError("Each VLAN needs a name.")
        entry: dict[str, Any] = {"name": name.strip()}
        tag = _opt_int(item, "vlan_tag")
        if tag is not None:
            entry["vlan_tag"] = tag
        desc = _opt_str(item, "description")
        if desc:
            entry["description"] = desc
        built.append(entry)
    summary = {
        "action": f"Create {len(built)} VLANs",
        "names": ", ".join(e["name"] for e in built[:10]),
    }
    return summary, {"method": "POST", "path": "/vlans/bulk-create", "body": {"items": built}}


async def _vlan_bulk_delete(session: AsyncSession, args: dict[str, Any]) -> BuiltAction:
    names_arg = args.get("names")
    if not isinstance(names_arg, list) or not names_arg:
        raise ActionError("Provide a non-empty 'names' list of VLANs to delete.")
    names = [str(x).strip() for x in names_arg if str(x).strip()]
    if not names:
        raise ActionError("Provide a non-empty 'names' list of VLANs to delete.")
    wanted = {n.lower() for n in names}
    stored = (await session.execute(select(VLAN.name))).scalars().all()
    matched = [n for n in stored if n.lower() in wanted]
    if not matched:
        raise ActionError("No VLANs found for those names.")
    summary = {
        "action": f"Delete {len(matched)} of {len(names)} VLANs",
        "names": ", ".join(sorted(matched)[:10]),
    }
    return summary, {"method": "POST", "path": "/vlans/bulk-delete", "body": {"names": names}}


async def _iprange_bulk_create(session: AsyncSession, args: dict[str, Any]) -> BuiltAction:
    items = args.get("items")
    if not isinstance(items, list) or not items:
        raise ActionError("Provide a non-empty 'items' list of IP ranges to create.")
    built: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            raise ActionError("Each item must be an object with at least a cidr.")
        cidr = item.get("cidr")
        if not isinstance(cidr, str) or not cidr.strip():
            raise ActionError("Each IP range needs a cidr.")
        entry: dict[str, Any] = {"cidr": cidr.strip()}
        vlan_name = _opt_str(item, "vlan_name")
        if vlan_name:
            entry["vlan_name"] = vlan_name
        desc = _opt_str(item, "description")
        if desc:
            entry["description"] = desc
        built.append(entry)
    summary = {
        "action": f"Create {len(built)} IP ranges",
        "cidrs": ", ".join(e["cidr"] for e in built[:10]),
    }
    return summary, {
        "method": "POST",
        "path": "/ip-ranges/bulk-create",
        "body": {"items": built},
    }


async def _iprange_bulk_delete(session: AsyncSession, args: dict[str, Any]) -> BuiltAction:
    cidrs_arg = args.get("cidrs")
    if not isinstance(cidrs_arg, list) or not cidrs_arg:
        raise ActionError("Provide a non-empty 'cidrs' list of IP ranges to delete.")
    cidrs = [str(x).strip() for x in cidrs_arg if str(x).strip()]
    if not cidrs:
        raise ActionError("Provide a non-empty 'cidrs' list of IP ranges to delete.")
    normalized = set()
    for c in cidrs:
        try:
            normalized.add(str(ipaddress.ip_network(c, strict=False)))
        except ValueError:
            continue  # invalid CIDR matches nothing; the endpoint reports it
    stored = (await session.execute(select(IPRange.cidr))).scalars().all()
    matched = sum(1 for r in stored if r in normalized)
    if matched == 0:
        raise ActionError("No IP ranges found for those CIDRs.")
    summary = {
        "action": f"Delete {matched} IP ranges",
        "cidrs": ", ".join(cidrs[:10]),
    }
    return summary, {
        "method": "POST",
        "path": "/ip-ranges/bulk-delete",
        "body": {"cidrs": cidrs},
    }


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


async def _find_asset_by_ip(session: AsyncSession, ip: str) -> Asset:
    row = (
        await session.execute(select(Asset).where(Asset.ip == ip))
    ).scalars().first()
    if row is None:
        raise ActionError(f"Asset '{ip}' not found.")
    return row


async def _asset_update(session: AsyncSession, args: dict[str, Any]) -> BuiltAction:
    """Patch an existing asset, resolved by its current IP. Only the fields the
    model actually supplied are sent, so untouched attributes are never cleared."""
    ip = _req_str(args, "ip")
    asset = await _find_asset_by_ip(session, ip)
    body: dict[str, Any] = {}
    summary: dict[str, Any] = {"ip": ip}

    new_ip = _opt_str(args, "new_ip")
    if new_ip:
        body["ip"] = new_ip
        summary["new_ip"] = new_ip
    hostname = _opt_str(args, "hostname")
    if hostname:
        body["hostname"] = hostname
        summary["hostname"] = hostname
    vlan_name = _opt_str(args, "vlan_name")
    if vlan_name:
        body["vlan_id"] = await _vlan_id_by_name(session, vlan_name)
        summary["vlan"] = vlan_name
    owner_email = _opt_str(args, "owner_email")
    if owner_email:
        body["owner_id"] = await _user_id_by_email(session, owner_email)
        summary["owner"] = owner_email
    criticality = _enum(args, "criticality", _CRITICALITIES, None)
    if criticality:
        body["criticality"] = criticality
        summary["criticality"] = criticality
    sensitivity = _enum(args, "data_sensitivity", _SENSITIVITIES, None)
    if sensitivity:
        body["data_sensitivity"] = sensitivity
        summary["data_sensitivity"] = sensitivity
    description = _opt_str(args, "description")
    if description:
        body["description"] = description
        summary["description"] = description

    if not body:
        raise ActionError("Nothing to update: provide at least one field to change.")

    return summary, {"method": "PATCH", "path": f"/assets/{asset.id}", "body": body}


async def _asset_bulk_create(session: AsyncSession, args: dict[str, Any]) -> BuiltAction:
    """Add several assets in one action. Each item needs an ip; hostname and
    classification are optional. Existing IPs are skipped at execution time."""
    items = args.get("items")
    if not isinstance(items, list) or not items:
        raise ActionError("Provide a non-empty 'items' list of assets to create.")
    built: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            raise ActionError("Each item must be an object with at least an ip.")
        ip = item.get("ip")
        if not isinstance(ip, str) or not ip.strip():
            raise ActionError("Each asset needs an ip.")
        entry: dict[str, Any] = {"ip": ip.strip()}
        hostname = _opt_str(item, "hostname")
        if hostname:
            entry["hostname"] = hostname
        criticality = _enum(item, "criticality", _CRITICALITIES, None)
        if criticality:
            entry["criticality"] = criticality
        sensitivity = _enum(item, "data_sensitivity", _SENSITIVITIES, None)
        if sensitivity:
            entry["data_sensitivity"] = sensitivity
        built.append(entry)
    preview = ", ".join(e["ip"] for e in built[:10])
    summary = {"action": f"Create {len(built)} assets", "ips": preview}
    return summary, {"method": "POST", "path": "/assets/bulk-create", "body": {"items": built}}


async def _asset_bulk_delete(session: AsyncSession, args: dict[str, Any]) -> BuiltAction:
    """Delete several assets by IP in one action. The summary previews how many
    of the given IPs actually exist, so the confirm card shows the blast radius
    before anything is deleted."""
    ips_arg = args.get("ips")
    if not isinstance(ips_arg, list) or not ips_arg:
        raise ActionError("Provide a non-empty 'ips' list of assets to delete.")
    ips = [str(x).strip() for x in ips_arg if str(x).strip()]
    if not ips:
        raise ActionError("Provide a non-empty 'ips' list of assets to delete.")
    matched = (
        await session.execute(select(Asset.ip).where(Asset.ip.in_(ips)))
    ).scalars().all()
    if not matched:
        raise ActionError("No assets found for those IPs.")
    summary = {
        "action": f"Delete {len(matched)} of {len(ips)} assets",
        "ips": ", ".join(sorted(matched)[:10]),
    }
    return summary, {"method": "POST", "path": "/assets/bulk-delete", "body": {"ips": ips}}


async def _asset_bulk_update(session: AsyncSession, args: dict[str, Any]) -> BuiltAction:
    """Apply the same field changes to several assets by IP. Only supplied fields
    are sent; the summary previews how many of the IPs actually exist."""
    ips_arg = args.get("ips")
    if not isinstance(ips_arg, list) or not ips_arg:
        raise ActionError("Provide a non-empty 'ips' list of assets to update.")
    ips = [str(x).strip() for x in ips_arg if str(x).strip()]
    if not ips:
        raise ActionError("Provide a non-empty 'ips' list of assets to update.")

    body: dict[str, Any] = {"ips": ips}
    summary: dict[str, Any] = {}
    criticality = _enum(args, "criticality", _CRITICALITIES, None)
    if criticality:
        body["criticality"] = criticality
        summary["criticality"] = criticality
    sensitivity = _enum(args, "data_sensitivity", _SENSITIVITIES, None)
    if sensitivity:
        body["data_sensitivity"] = sensitivity
        summary["data_sensitivity"] = sensitivity
    owner_email = _opt_str(args, "owner_email")
    if owner_email:
        body["owner_id"] = await _user_id_by_email(session, owner_email)
        summary["owner"] = owner_email
    vlan_name = _opt_str(args, "vlan_name")
    if vlan_name:
        body["vlan_id"] = await _vlan_id_by_name(session, vlan_name)
        summary["vlan"] = vlan_name
    if len(body) == 1:  # only "ips"
        raise ActionError("Provide at least one field to change (criticality, owner, ...).")

    matched = (
        await session.execute(select(Asset.ip).where(Asset.ip.in_(ips)))
    ).scalars().all()
    if not matched:
        raise ActionError("No assets found for those IPs.")
    summary = {"action": f"Update {len(matched)} of {len(ips)} assets", **summary}
    return summary, {"method": "POST", "path": "/assets/bulk-update", "body": body}


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


async def _find_change(
    session: AsyncSession, args: dict[str, Any]
) -> tuple[ChangeEvent, str]:
    """Resolve a change by its host:port/proto (a natural key the model can read
    from the snapshot), returning the most recent match."""
    ip = _req_str(args, "ip")
    port = _opt_int(args, "port")
    if port is None:
        raise ActionError("'port' is required.")
    protocol = (_opt_str(args, "protocol") or "tcp").lower()
    row = (
        await session.execute(
            select(ChangeEvent)
            .where(
                ChangeEvent.ip == ip,
                ChangeEvent.port == port,
                func.lower(ChangeEvent.protocol) == protocol,
            )
            .order_by(ChangeEvent.detected_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if row is None:
        raise ActionError(f"No change found for {ip}:{port}/{protocol}.")
    return row, f"{ip}:{port}/{protocol}"


async def _change_acknowledge(session: AsyncSession, args: dict[str, Any]) -> BuiltAction:
    row, target = await _find_change(session, args)
    summary = {"target": target, "status": "acknowledged"}
    return summary, {
        "method": "PATCH",
        "path": f"/changes/{row.id}",
        "body": {"status": "acknowledged"},
    }


async def _change_resolve(session: AsyncSession, args: dict[str, Any]) -> BuiltAction:
    row, target = await _find_change(session, args)
    summary = {"target": target, "status": "resolved"}
    return summary, {
        "method": "PATCH",
        "path": f"/changes/{row.id}",
        "body": {"status": "resolved"},
    }


async def _find_task(session: AsyncSession, title: str) -> Task:
    row = (
        await session.execute(
            select(Task)
            .where(func.lower(Task.title) == title.lower())
            .order_by(Task.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if row is None:
        raise ActionError(f"Task '{title}' not found.")
    return row


async def _task_update_status(session: AsyncSession, args: dict[str, Any]) -> BuiltAction:
    title = _req_str(args, "title")
    status = _enum(args, "status", _TASK_STATUSES, None)
    if status is None:
        raise ActionError("'status' is required.")
    row = await _find_task(session, title)
    summary = {"title": row.title, "status": status}
    return summary, {
        "method": "PATCH",
        "path": f"/tasks/{row.id}",
        "body": {"status": status},
    }


async def _task_link_jira(session: AsyncSession, args: dict[str, Any]) -> BuiltAction:
    title = _req_str(args, "title")
    row = await _find_task(session, title)
    return {"title": row.title}, {
        "method": "POST",
        "path": f"/tasks/{row.id}/jira",
        "body": None,
    }


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
        "vlan.bulk_create",
        WRITE_ROLES,
        "Add several VLANs at once. Existing names are skipped.",
        "items: list of {name (required), vlan_tag (number, optional), "
        "description (optional)}",
        _vlan_bulk_create,
    ),
    ActionSpec(
        "vlan.bulk_delete",
        WRITE_ROLES,
        "Delete several VLANs by name at once. The confirm card shows how many "
        "match before you run it.",
        "names: list of VLAN names (required)",
        _vlan_bulk_delete,
    ),
    ActionSpec(
        "iprange.create",
        WRITE_ROLES,
        "Create an IP range (CIDR block).",
        "cidr (required), vlan_name (optional), description (optional)",
        _iprange_create,
    ),
    ActionSpec(
        "iprange.bulk_create",
        WRITE_ROLES,
        "Add several IP ranges at once. CIDRs already present are skipped.",
        "items: list of {cidr (required), vlan_name (optional), "
        "description (optional)}",
        _iprange_bulk_create,
    ),
    ActionSpec(
        "iprange.bulk_delete",
        WRITE_ROLES,
        "Delete several IP ranges by CIDR at once. The confirm card shows how "
        "many match before you run it.",
        "cidrs: list of CIDR blocks (required)",
        _iprange_bulk_delete,
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
        "asset.update",
        WRITE_ROLES,
        "Update an existing asset, found by its current IP. Send only the fields to change.",
        "ip (required, the asset's current IP), new_ip (optional, to change the "
        "address), hostname (optional), vlan_name (optional), owner_email "
        "(optional), criticality (low|medium|high|critical, optional), "
        "data_sensitivity (none|pii|cde|ephi, optional), description (optional)",
        _asset_update,
    ),
    ActionSpec(
        "asset.bulk_create",
        WRITE_ROLES,
        "Add several assets (hosts) at once. Existing IPs are skipped.",
        "items: list of {ip (required), hostname (optional), criticality "
        "(low|medium|high|critical, optional), data_sensitivity "
        "(none|pii|cde|ephi, optional)}",
        _asset_bulk_create,
    ),
    ActionSpec(
        "asset.bulk_delete",
        WRITE_ROLES,
        "Delete several assets by IP at once. The confirm card shows how many "
        "match before you run it.",
        "ips: list of IP addresses (required)",
        _asset_bulk_delete,
    ),
    ActionSpec(
        "asset.bulk_update",
        WRITE_ROLES,
        "Change the same fields on several assets by IP at once (bulk edit).",
        "ips: list of IP addresses (required); then any of criticality "
        "(low|medium|high|critical), data_sensitivity (none|pii|cde|ephi), "
        "owner_email, vlan_name",
        _asset_bulk_update,
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
    ActionSpec(
        "change.acknowledge",
        WRITE_ROLES,
        "Acknowledge a confirmed change (identified by host:port).",
        "ip (required), port (required), protocol (optional, default tcp)",
        _change_acknowledge,
    ),
    ActionSpec(
        "change.resolve",
        WRITE_ROLES,
        "Resolve a confirmed change (identified by host:port).",
        "ip (required), port (required), protocol (optional, default tcp)",
        _change_resolve,
    ),
    ActionSpec(
        "task.update_status",
        WRITE_ROLES,
        "Change a task's status.",
        "title (required), status (open|in_progress|done|cancelled, required)",
        _task_update_status,
    ),
    ActionSpec(
        "task.link_jira",
        WRITE_ROLES,
        "Create and link a Jira issue for a task.",
        "title (required)",
        _task_link_jira,
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
    asset_rows = (
        await session.execute(
            select(Asset.ip, Asset.hostname, Asset.criticality).order_by(Asset.ip).limit(15)
        )
    ).all()
    asset_labels = [
        ip
        + (f" ({hostname})" if hostname else "")
        + f" [{getattr(crit, 'value', crit)}]"
        for ip, hostname, crit in asset_rows
    ]
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
    open_tasks_total = await count(Task, Task.status.in_(["open", "in_progress"]))
    pending_runs = await count(ScanRun, ScanRun.status == "pending")

    change_rows = (
        await session.execute(
            select(
                ChangeEvent.ip,
                ChangeEvent.port,
                ChangeEvent.protocol,
                ChangeEvent.change_type,
                ChangeEvent.severity,
            )
            .where(ChangeEvent.status == "open")
            .order_by(ChangeEvent.detected_at.desc())
            .limit(10)
        )
    ).all()
    change_labels = [
        f"{ip}:{port}/{proto} {ctype} ({sev})"
        for ip, port, proto, ctype, sev in change_rows
    ]
    task_titles = (
        await session.execute(
            select(Task.title)
            .where(Task.status.in_(["open", "in_progress"]))
            .order_by(Task.created_at.desc())
            .limit(10)
        )
    ).scalars().all()

    now = dt.datetime.now(tz=dt.timezone.utc)
    agent_labels = [
        f"{name} ({'online' if _is_online(ls, now) else 'offline' if enabled else 'disabled'})"
        for name, enabled, ls in agent_rows
    ]
    return "\n".join(
        [
            f"Assets ({n_assets}): {', '.join(asset_labels) or 'none'}",
            f"VLANs ({len(vlan_names)}): {', '.join(vlan_names) or 'none'}",
            f"Scan profiles ({len(profile_names)}): {', '.join(profile_names) or 'none'}",
            f"Agents ({len(agent_labels)}): {', '.join(agent_labels) or 'none'}",
            f"Open changes ({open_changes}): {'; '.join(change_labels) or 'none'}",
            f"Open tasks ({open_tasks_total}): {'; '.join(task_titles) or 'none'}",
            f"Pending scan runs: {pending_runs}",
        ]
    )
