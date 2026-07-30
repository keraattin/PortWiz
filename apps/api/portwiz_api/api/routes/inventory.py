"""Asset inventory CRUD: VLANs, IP ranges, and assets.

Reads are available to any authenticated user; writes require admin or operator.
Every create/update/delete is recorded in the immutable audit log.
"""

from __future__ import annotations

import datetime as dt
import ipaddress
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.app_settings import effective_settings
from ...core.asset_import import parse_asset_file
from ...core.asset_store import upsert_asset
from ...core.audit import append_audit, field_diff
from ...core.db import get_session
from ...core.inventory_source import (
    InventorySource,
    SourceAsset,
    get_inventory_source,
)
from ...core.vlan_import import parse_vlan_file
from ...models.asset import VLAN, Asset, IPRange
from ...models.user import User, UserRole
from ...schemas.asset import (
    AssetBulkCreate,
    AssetBulkDelete,
    AssetBulkReport,
    AssetCreate,
    AssetImportReport,
    AssetImportRowResult,
    AssetPushReport,
    AssetRead,
    AssetSyncReport,
    AssetUpdate,
    IPRangeCreate,
    IPRangeRead,
    IPRangeUpdate,
    VLANCreate,
    VLANImportReport,
    VLANImportRowResult,
    VLANRead,
    VlanSyncReport,
    VLANUpdate,
)
from ..deps import get_current_user, require_roles

# Cap upload size so a huge file can't exhaust memory during parsing.
MAX_IMPORT_BYTES = 5 * 1024 * 1024

# Writes are restricted to admin/operator; reads to any authenticated user.
WriteDep = require_roles(UserRole.admin, UserRole.operator)


def _utcnow() -> dt.datetime:
    return dt.datetime.now(tz=dt.timezone.utc)


# VLANs
vlans_router = APIRouter(prefix="/vlans", tags=["inventory"])


@vlans_router.get("", response_model=list[VLANRead])
async def list_vlans(
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[VLAN]:
    result = await session.execute(select(VLAN).order_by(VLAN.name))
    return list(result.scalars().all())


@vlans_router.post("", response_model=VLANRead, status_code=status.HTTP_201_CREATED)
async def create_vlan(
    payload: VLANCreate,
    current_user: User = Depends(WriteDep),
    session: AsyncSession = Depends(get_session),
) -> VLAN:
    existing = (
        await session.execute(select(VLAN).where(VLAN.name == payload.name))
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "VLAN name already exists")

    vlan = VLAN(**payload.model_dump())
    session.add(vlan)
    await session.flush()
    await append_audit(
        session,
        action="vlan.created",
        actor_id=current_user.id,
        actor_email=current_user.email,
        target_type="vlan",
        target_id=str(vlan.id),
        payload={"name": vlan.name, "vlan_tag": vlan.vlan_tag},
    )
    await session.commit()
    await session.refresh(vlan)
    return vlan


_VLAN_TEMPLATE_CSV = (
    "name,tag,description\r\n"
    "DMZ,10,Internet-facing servers\r\n"
    "Servers,20,Internal application servers\r\n"
)


@vlans_router.get("/import-template")
async def vlan_import_template(_: User = Depends(get_current_user)) -> Response:
    """A ready-to-fill CSV with the VLAN import columns and example rows."""
    return Response(
        content=_VLAN_TEMPLATE_CSV,
        media_type="text/csv",
        headers={
            "Content-Disposition": 'attachment; filename="portwiz-vlans-template.csv"'
        },
    )


@vlans_router.post("/import", response_model=VLANImportReport)
async def import_vlans(
    file: UploadFile = File(...),
    on_conflict: str = Query("update", pattern="^(update|skip)$"),
    current_user: User = Depends(WriteDep),
    session: AsyncSession = Depends(get_session),
) -> VLANImportReport:
    """Bulk-create or update VLANs from a CSV or .xlsx upload, upserting by name.

    A per-row report is returned and one summary event is appended to the audit
    log. Tags are validated to the 802.1Q range (1-4094)."""
    content = await file.read()
    if len(content) > MAX_IMPORT_BYTES:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "File too large (max 5 MB)"
        )
    try:
        rows = parse_vlan_file(content, file.filename or "")
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc

    by_name = {
        v.name.lower(): v for v in (await session.execute(select(VLAN))).scalars()
    }

    results: list[VLANImportRowResult] = []
    created = updated = skipped = errors = 0
    for parsed in rows:
        name = parsed.values.get("name")
        if parsed.error:
            errors += 1
            results.append(
                VLANImportRowResult(row=parsed.row, name=name, status="error", error=parsed.error)
            )
            continue

        values = parsed.values
        fields: dict[str, object] = {"name": values["name"]}
        if "tag" in values:
            fields["vlan_tag"] = int(values["tag"])
        if "description" in values:
            fields["description"] = values["description"]

        existing = by_name.get(values["name"].lower())
        if existing is not None:
            if on_conflict == "skip":
                skipped += 1
                results.append(VLANImportRowResult(row=parsed.row, name=name, status="skipped"))
                continue
            for key, value in fields.items():
                setattr(existing, key, value)
            updated += 1
            results.append(VLANImportRowResult(row=parsed.row, name=name, status="updated"))
        else:
            vlan = VLAN(**fields)
            session.add(vlan)
            await session.flush()
            by_name[values["name"].lower()] = vlan
            created += 1
            results.append(VLANImportRowResult(row=parsed.row, name=name, status="created"))

    await append_audit(
        session,
        action="vlan.imported",
        actor_id=current_user.id,
        actor_email=current_user.email,
        target_type="vlan",
        target_id=None,
        payload={"total": len(rows), "created": created, "updated": updated, "errors": errors},
    )
    await session.commit()
    return VLANImportReport(
        total=len(rows),
        created=created,
        updated=updated,
        skipped=skipped,
        errors=errors,
        results=results,
    )


@vlans_router.post("/sync", response_model=VlanSyncReport)
async def sync_vlans(
    on_conflict: str = Query("update", pattern="^(update|skip)$"),
    current_user: User = Depends(WriteDep),
    session: AsyncSession = Depends(get_session),
    source: InventorySource = Depends(get_inventory_source),
) -> VlanSyncReport:
    """Pull VLANs from the configured external inventory source (NetBox) and
    upsert them by name. Returns a summary; one vlan.synced event is audited."""
    if source.name == "none":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No inventory source is configured.")
    eff = await effective_settings(session)
    if not eff.netbox_import_vlans:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "VLAN import from NetBox is disabled."
        )
    try:
        items = await source.fetch_vlans()
    except Exception as exc:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, f"Inventory source unavailable: {exc}"
        ) from exc

    by_name = {v.name.lower(): v for v in (await session.execute(select(VLAN))).scalars()}

    created = updated = skipped = errors = 0
    errors_detail: list[str] = []
    for item in items:
        tag = item.tag
        if tag is not None and not (1 <= tag <= 4094):
            errors += 1
            errors_detail.append(f"VLAN '{item.name}' has out-of-range tag {tag}")
            continue
        fields: dict[str, object] = {"name": item.name}
        if tag is not None:
            fields["vlan_tag"] = tag
        if item.description and eff.netbox_import_descriptions:
            fields["description"] = item.description

        existing = by_name.get(item.name.lower())
        if existing is not None:
            if on_conflict == "skip":
                skipped += 1
                continue
            for key, value in fields.items():
                setattr(existing, key, value)
            updated += 1
        else:
            vlan = VLAN(**fields)
            session.add(vlan)
            await session.flush()
            by_name[item.name.lower()] = vlan
            created += 1

    await append_audit(
        session,
        action="vlan.synced",
        actor_id=current_user.id,
        actor_email=current_user.email,
        target_type="vlan",
        target_id=None,
        payload={
            "source": source.name,
            "total": len(items),
            "created": created,
            "updated": updated,
            "skipped": skipped,
            "errors": errors,
        },
    )
    await session.commit()
    return VlanSyncReport(
        source=source.name,
        total=len(items),
        created=created,
        updated=updated,
        skipped=skipped,
        errors=errors,
        errors_detail=errors_detail[:50],
    )


@vlans_router.patch("/{vlan_id}", response_model=VLANRead)
async def update_vlan(
    vlan_id: uuid.UUID,
    payload: VLANUpdate,
    current_user: User = Depends(WriteDep),
    session: AsyncSession = Depends(get_session),
) -> VLAN:
    vlan = await session.get(VLAN, vlan_id)
    if vlan is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "VLAN not found")
    changes = payload.model_dump(exclude_unset=True)
    before = {key: getattr(vlan, key) for key in changes}
    for key, value in changes.items():
        setattr(vlan, key, value)
    await append_audit(
        session,
        action="vlan.updated",
        actor_id=current_user.id,
        actor_email=current_user.email,
        target_type="vlan",
        target_id=str(vlan.id),
        payload={"vlan": vlan.name, "changes": field_diff(before, changes)},
    )
    await session.commit()
    await session.refresh(vlan)
    return vlan


@vlans_router.delete("/{vlan_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_vlan(
    vlan_id: uuid.UUID,
    current_user: User = Depends(WriteDep),
    session: AsyncSession = Depends(get_session),
) -> None:
    vlan = await session.get(VLAN, vlan_id)
    if vlan is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "VLAN not found")
    await session.delete(vlan)
    await append_audit(
        session,
        action="vlan.deleted",
        actor_id=current_user.id,
        actor_email=current_user.email,
        target_type="vlan",
        target_id=str(vlan_id),
    )
    await session.commit()


# IP ranges
ip_ranges_router = APIRouter(prefix="/ip-ranges", tags=["inventory"])


@ip_ranges_router.get("", response_model=list[IPRangeRead])
async def list_ip_ranges(
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[IPRange]:
    result = await session.execute(select(IPRange).order_by(IPRange.cidr))
    return list(result.scalars().all())


@ip_ranges_router.post("", response_model=IPRangeRead, status_code=status.HTTP_201_CREATED)
async def create_ip_range(
    payload: IPRangeCreate,
    current_user: User = Depends(WriteDep),
    session: AsyncSession = Depends(get_session),
) -> IPRange:
    if payload.vlan_id is not None and await session.get(VLAN, payload.vlan_id) is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Referenced VLAN does not exist")

    ip_range = IPRange(**payload.model_dump())
    session.add(ip_range)
    await session.flush()
    await append_audit(
        session,
        action="ip_range.created",
        actor_id=current_user.id,
        actor_email=current_user.email,
        target_type="ip_range",
        target_id=str(ip_range.id),
        payload={"cidr": ip_range.cidr},
    )
    await session.commit()
    await session.refresh(ip_range)
    return ip_range


@ip_ranges_router.patch("/{ip_range_id}", response_model=IPRangeRead)
async def update_ip_range(
    ip_range_id: uuid.UUID,
    payload: IPRangeUpdate,
    current_user: User = Depends(WriteDep),
    session: AsyncSession = Depends(get_session),
) -> IPRange:
    ip_range = await session.get(IPRange, ip_range_id)
    if ip_range is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "IP range not found")
    changes = payload.model_dump(exclude_unset=True)
    if "vlan_id" in changes and changes["vlan_id"] is not None:
        if await session.get(VLAN, changes["vlan_id"]) is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Referenced VLAN does not exist")
    before = {key: getattr(ip_range, key) for key in changes}
    for key, value in changes.items():
        setattr(ip_range, key, value)
    await append_audit(
        session,
        action="ip_range.updated",
        actor_id=current_user.id,
        actor_email=current_user.email,
        target_type="ip_range",
        target_id=str(ip_range.id),
        payload={"cidr": ip_range.cidr, "changes": field_diff(before, changes)},
    )
    await session.commit()
    await session.refresh(ip_range)
    return ip_range


@ip_ranges_router.delete("/{ip_range_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_ip_range(
    ip_range_id: uuid.UUID,
    current_user: User = Depends(WriteDep),
    session: AsyncSession = Depends(get_session),
) -> None:
    ip_range = await session.get(IPRange, ip_range_id)
    if ip_range is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "IP range not found")
    await session.delete(ip_range)
    await append_audit(
        session,
        action="ip_range.deleted",
        actor_id=current_user.id,
        actor_email=current_user.email,
        target_type="ip_range",
        target_id=str(ip_range_id),
    )
    await session.commit()


# Assets
assets_router = APIRouter(prefix="/assets", tags=["inventory"])


async def _validate_asset_refs(
    session: AsyncSession, vlan_id: uuid.UUID | None, owner_id: uuid.UUID | None
) -> None:
    if vlan_id is not None and await session.get(VLAN, vlan_id) is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Referenced VLAN does not exist")
    if owner_id is not None and await session.get(User, owner_id) is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Referenced owner does not exist")


def _asset_kwargs(
    values: dict[str, str], vlan_id: uuid.UUID | None, owner_id: uuid.UUID | None
) -> dict[str, object]:
    """Map a parsed import row to Asset fields, keeping only present columns so
    an upsert never clobbers an existing value with a default."""
    kwargs: dict[str, object] = {"ip": values["ip"]}
    if "hostname" in values:
        kwargs["hostname"] = values["hostname"]
    if "vlan" in values:
        kwargs["vlan_id"] = vlan_id
    if "owner" in values:
        kwargs["owner_id"] = owner_id
    if "criticality" in values:
        kwargs["criticality"] = values["criticality"]
    if "data_sensitivity" in values:
        kwargs["data_sensitivity"] = values["data_sensitivity"]
    if "description" in values:
        kwargs["description"] = values["description"]
    return kwargs


@assets_router.get("", response_model=list[AssetRead])
async def list_assets(
    vlan_id: uuid.UUID | None = None,
    owner_id: uuid.UUID | None = None,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[Asset]:
    query = select(Asset).order_by(Asset.ip)
    if vlan_id is not None:
        query = query.where(Asset.vlan_id == vlan_id)
    if owner_id is not None:
        query = query.where(Asset.owner_id == owner_id)
    result = await session.execute(query)
    return list(result.scalars().all())


_IMPORT_TEMPLATE_CSV = (
    "ip,hostname,vlan,owner,criticality,data_sensitivity,description\r\n"
    "10.0.0.10,web-01,DMZ,owner@example.com,high,cde,Internet-facing web server\r\n"
    "10.0.0.11,db-01,Servers,owner@example.com,critical,pii,Primary database\r\n"
)


# Declared before /{asset_id} so the literal path is not captured as an id.
@assets_router.get("/import-template")
async def asset_import_template(_: User = Depends(get_current_user)) -> Response:
    """A ready-to-fill CSV with the import columns and example rows. Opens in
    Excel; the import accepts the same columns as .csv or .xlsx."""
    return Response(
        content=_IMPORT_TEMPLATE_CSV,
        media_type="text/csv",
        headers={
            "Content-Disposition": 'attachment; filename="portwiz-assets-template.csv"'
        },
    )


@assets_router.get("/{asset_id}", response_model=AssetRead)
async def get_asset(
    asset_id: uuid.UUID,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Asset:
    asset = await session.get(Asset, asset_id)
    if asset is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Asset not found")
    return asset


@assets_router.post("", response_model=AssetRead, status_code=status.HTTP_201_CREATED)
async def create_asset(
    payload: AssetCreate,
    current_user: User = Depends(WriteDep),
    session: AsyncSession = Depends(get_session),
) -> Asset:
    await _validate_asset_refs(session, payload.vlan_id, payload.owner_id)
    asset = Asset(**payload.model_dump())
    session.add(asset)
    await session.flush()
    await append_audit(
        session,
        action="asset.created",
        actor_id=current_user.id,
        actor_email=current_user.email,
        target_type="asset",
        target_id=str(asset.id),
        payload={
            "ip": asset.ip,
            "criticality": asset.criticality,
            "owner_id": str(asset.owner_id) if asset.owner_id else None,
        },
    )
    await session.commit()
    await session.refresh(asset)
    return asset


@assets_router.post("/import", response_model=AssetImportReport)
async def import_assets(
    file: UploadFile = File(...),
    on_conflict: str = Query("update", pattern="^(update|skip)$"),
    current_user: User = Depends(WriteDep),
    session: AsyncSession = Depends(get_session),
) -> AssetImportReport:
    """Bulk-create or update assets from a CSV or .xlsx upload.

    Rows are upserted by IP (``on_conflict`` controls update vs skip). VLANs are
    matched by name and owners by email; an unknown reference fails just that
    row. A per-row report is returned, and one summary event is appended to the
    audit log.
    """
    content = await file.read()
    if len(content) > MAX_IMPORT_BYTES:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "File too large (max 5 MB)"
        )
    try:
        rows = parse_asset_file(content, file.filename or "")
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc

    # Preload lookup maps so reference resolution is O(1) per row.
    vlan_by_name = {
        v.name.lower(): v.id for v in (await session.execute(select(VLAN))).scalars()
    }
    user_by_email = {
        u.email.lower(): u.id for u in (await session.execute(select(User))).scalars()
    }

    results: list[AssetImportRowResult] = []
    created = updated = skipped = errors = 0

    for parsed in rows:
        ip = parsed.values.get("ip")
        if parsed.error:
            errors += 1
            results.append(
                AssetImportRowResult(row=parsed.row, ip=ip, status="error", error=parsed.error)
            )
            continue

        values = parsed.values
        vlan_id: uuid.UUID | None = None
        if "vlan" in values:
            vlan_id = vlan_by_name.get(values["vlan"].lower())
            if vlan_id is None:
                errors += 1
                results.append(
                    AssetImportRowResult(
                        row=parsed.row, ip=ip, status="error",
                        error=f"Unknown VLAN '{values['vlan']}'",
                    )
                )
                continue
        owner_id: uuid.UUID | None = None
        if "owner" in values:
            owner_id = user_by_email.get(values["owner"].lower())
            if owner_id is None:
                errors += 1
                results.append(
                    AssetImportRowResult(
                        row=parsed.row, ip=ip, status="error",
                        error=f"Unknown owner '{values['owner']}'",
                    )
                )
                continue

        kwargs = _asset_kwargs(values, vlan_id, owner_id)
        existing = (
            await session.execute(select(Asset).where(Asset.ip == values["ip"]))
        ).scalars().first()
        if existing is not None:
            if on_conflict == "skip":
                skipped += 1
                results.append(AssetImportRowResult(row=parsed.row, ip=ip, status="skipped"))
                continue
            for key, value in kwargs.items():
                setattr(existing, key, value)
            existing.updated_at = _utcnow()
            updated += 1
            results.append(AssetImportRowResult(row=parsed.row, ip=ip, status="updated"))
        else:
            session.add(Asset(**kwargs))
            # Flush so a later row with the same IP upserts instead of duplicating.
            await session.flush()
            created += 1
            results.append(AssetImportRowResult(row=parsed.row, ip=ip, status="created"))

    await append_audit(
        session,
        action="asset.imported",
        actor_id=current_user.id,
        actor_email=current_user.email,
        target_type="asset",
        target_id=None,
        payload={
            "filename": file.filename,
            "total": len(rows),
            "created": created,
            "updated": updated,
            "skipped": skipped,
            "errors": errors,
        },
    )
    await session.commit()
    return AssetImportReport(
        total=len(rows),
        created=created,
        updated=updated,
        skipped=skipped,
        errors=errors,
        results=results,
    )


@assets_router.post("/sync", response_model=AssetSyncReport)
async def sync_assets(
    on_conflict: str = Query("update", pattern="^(update|skip)$"),
    current_user: User = Depends(WriteDep),
    session: AsyncSession = Depends(get_session),
    source: InventorySource = Depends(get_inventory_source),
) -> AssetSyncReport:
    """Pull hosts from the configured external inventory source (NetBox) and
    upsert them by IP. Returns a summary; one asset.synced event is audited."""
    if source.name == "none":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No inventory source is configured.")
    eff = await effective_settings(session)
    if not eff.netbox_import_assets:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Asset import from NetBox is disabled."
        )
    try:
        items = await source.fetch_assets()
    except Exception as exc:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, f"Inventory source unavailable: {exc}"
        ) from exc

    vlan_by_name = {
        v.name.lower(): v.id for v in (await session.execute(select(VLAN))).scalars()
    }

    created = updated = skipped = errors = 0
    errors_detail: list[str] = []
    for item in items:
        try:
            ipaddress.ip_address(item.ip)
        except ValueError:
            errors += 1
            errors_detail.append(f"Invalid IP '{item.ip}'")
            continue
        fields: dict[str, object] = {}
        if item.hostname and eff.netbox_import_hostnames:
            fields["hostname"] = item.hostname
        if item.description and eff.netbox_import_descriptions:
            fields["description"] = item.description
        if item.vlan_name:
            vlan_id = vlan_by_name.get(item.vlan_name.lower())
            if vlan_id is not None:
                fields["vlan_id"] = vlan_id
        outcome = await upsert_asset(session, item.ip, fields, on_conflict)
        if outcome == "created":
            created += 1
        elif outcome == "updated":
            updated += 1
        else:
            skipped += 1

    await append_audit(
        session,
        action="asset.synced",
        actor_id=current_user.id,
        actor_email=current_user.email,
        target_type="asset",
        target_id=None,
        payload={
            "source": source.name,
            "total": len(items),
            "created": created,
            "updated": updated,
            "skipped": skipped,
            "errors": errors,
        },
    )
    await session.commit()
    return AssetSyncReport(
        source=source.name,
        total=len(items),
        created=created,
        updated=updated,
        skipped=skipped,
        errors=errors,
        errors_detail=errors_detail[:50],
    )


@assets_router.post("/push-netbox", response_model=AssetPushReport)
async def push_assets_to_netbox(
    current_user: User = Depends(WriteDep),
    session: AsyncSession = Depends(get_session),
    source: InventorySource = Depends(get_inventory_source),
) -> AssetPushReport:
    """Write PortWiz's scan-discovered hosts back to NetBox as IP addresses,
    skipping any whose IP already exists there. Audited as asset.pushed."""
    if source.name == "none":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No inventory source is configured.")
    discovered = (
        (await session.execute(select(Asset).where(Asset.discovered.is_(True)))).scalars().all()
    )
    payload = [
        SourceAsset(ip=a.ip, hostname=a.hostname, description=a.description) for a in discovered
    ]
    try:
        result = await source.push_assets(payload)
    except Exception as exc:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, f"Inventory source unavailable: {exc}"
        ) from exc

    await append_audit(
        session,
        action="asset.pushed",
        actor_id=current_user.id,
        actor_email=current_user.email,
        target_type="asset",
        target_id=None,
        payload={
            "source": source.name,
            "total": len(payload),
            "created": result.created,
            "skipped": result.skipped,
            "errors": result.errors,
        },
    )
    await session.commit()
    return AssetPushReport(
        source=source.name,
        total=len(payload),
        created=result.created,
        skipped=result.skipped,
        errors=result.errors,
        errors_detail=result.errors_detail[:50],
    )


@assets_router.patch("/{asset_id}", response_model=AssetRead)
async def update_asset(
    asset_id: uuid.UUID,
    payload: AssetUpdate,
    current_user: User = Depends(WriteDep),
    session: AsyncSession = Depends(get_session),
) -> Asset:
    asset = await session.get(Asset, asset_id)
    if asset is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Asset not found")
    changes = payload.model_dump(exclude_unset=True)
    await _validate_asset_refs(
        session,
        changes.get("vlan_id") if "vlan_id" in changes else None,
        changes.get("owner_id") if "owner_id" in changes else None,
    )
    before = {key: getattr(asset, key) for key in changes}
    for key, value in changes.items():
        setattr(asset, key, value)
    asset.updated_at = _utcnow()
    await append_audit(
        session,
        action="asset.updated",
        actor_id=current_user.id,
        actor_email=current_user.email,
        target_type="asset",
        target_id=str(asset.id),
        payload={"ip": asset.ip, "changes": field_diff(before, changes)},
    )
    await session.commit()
    await session.refresh(asset)
    return asset


@assets_router.delete("/{asset_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_asset(
    asset_id: uuid.UUID,
    current_user: User = Depends(WriteDep),
    session: AsyncSession = Depends(get_session),
) -> None:
    asset = await session.get(Asset, asset_id)
    if asset is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Asset not found")
    await session.delete(asset)
    await append_audit(
        session,
        action="asset.deleted",
        actor_id=current_user.id,
        actor_email=current_user.email,
        target_type="asset",
        target_id=str(asset_id),
    )
    await session.commit()


@assets_router.post("/bulk-create", response_model=AssetBulkReport)
async def bulk_create_assets(
    payload: AssetBulkCreate,
    current_user: User = Depends(WriteDep),
    session: AsyncSession = Depends(get_session),
) -> AssetBulkReport:
    """Create many assets at once (assistant bulk add). Existing IPs are skipped
    and invalid IPs are reported per item; one audit entry records the batch."""
    created = skipped = errors = 0
    errors_detail: list[str] = []
    for item in payload.items:
        try:
            ipaddress.ip_address(item.ip)
        except ValueError:
            errors += 1
            errors_detail.append(f"Invalid IP '{item.ip}'")
            continue
        fields: dict[str, object] = {
            "criticality": item.criticality,
            "data_sensitivity": item.data_sensitivity,
        }
        if item.hostname:
            fields["hostname"] = item.hostname
        outcome = await upsert_asset(session, item.ip, fields, "skip")
        if outcome == "created":
            created += 1
        else:
            skipped += 1
    await append_audit(
        session,
        action="asset.bulk_created",
        actor_id=current_user.id,
        actor_email=current_user.email,
        target_type="asset",
        target_id=None,
        payload={
            "total": len(payload.items),
            "created": created,
            "skipped": skipped,
            "errors": errors,
        },
    )
    await session.commit()
    return AssetBulkReport(
        total=len(payload.items),
        succeeded=created,
        skipped=skipped,
        errors=errors,
        errors_detail=errors_detail[:50],
    )


@assets_router.post("/bulk-delete", response_model=AssetBulkReport)
async def bulk_delete_assets(
    payload: AssetBulkDelete,
    current_user: User = Depends(WriteDep),
    session: AsyncSession = Depends(get_session),
) -> AssetBulkReport:
    """Delete many assets by IP at once (assistant bulk delete). An IP with no
    matching asset is reported, not an error; one audit entry records the batch."""
    deleted = 0
    not_found: list[str] = []
    for ip in payload.ips:
        asset = (
            await session.execute(select(Asset).where(Asset.ip == ip))
        ).scalars().first()
        if asset is None:
            not_found.append(ip)
            continue
        await session.delete(asset)
        deleted += 1
    await append_audit(
        session,
        action="asset.bulk_deleted",
        actor_id=current_user.id,
        actor_email=current_user.email,
        target_type="asset",
        target_id=None,
        payload={"total": len(payload.ips), "deleted": deleted, "not_found": not_found},
    )
    await session.commit()
    return AssetBulkReport(
        total=len(payload.ips),
        succeeded=deleted,
        skipped=len(not_found),
        errors=0,
        errors_detail=not_found[:50],
    )
