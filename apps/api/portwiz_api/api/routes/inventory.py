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
from ...core.audit import append_audit, audit_value, field_diff
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
    AssetBulkUpdate,
    AssetCreate,
    AssetImportApply,
    AssetImportPreviewRow,
    AssetImportReport,
    AssetImportRowResult,
    AssetPreviewItem,
    AssetPushReport,
    AssetRead,
    AssetSyncApply,
    AssetSyncReport,
    AssetUpdate,
    BulkReport,
    IPRangeBulkCreate,
    IPRangeBulkDelete,
    IPRangeBulkUpdate,
    IPRangeCreate,
    IPRangePreviewItem,
    IPRangeRead,
    IPRangeSyncApply,
    IPRangeSyncReport,
    IPRangeUpdate,
    VlanBulkCreate,
    VlanBulkDelete,
    VlanBulkUpdate,
    VLANCreate,
    VlanImportApply,
    VlanImportPreviewRow,
    VLANImportReport,
    VLANImportRowResult,
    VlanPreviewItem,
    VLANRead,
    VlanSyncApply,
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
    "name,tag,description,cidr\r\n"
    "DMZ,10,Internet-facing servers,10.0.0.0/24\r\n"
    "Servers,20,Internal application servers,10.0.1.0/24\r\n"
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

    A VLAN and its IP ranges import as one unit: an optional ``cidr`` per row
    attaches that range to the row's VLAN (repeat the name to add several). A
    per-row report is returned and one summary event is appended to the audit
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
    # Existing ranges, so a re-import does not duplicate a CIDR that is already in.
    existing_ranges = {
        r.cidr for r in (await session.execute(select(IPRange))).scalars()
    }

    results: list[VLANImportRowResult] = []
    created = updated = skipped = errors = 0
    ranges_created = ranges_skipped = 0
    for parsed in rows:
        name = parsed.values.get("name")
        cidr = parsed.values.get("cidr")
        if parsed.error:
            errors += 1
            results.append(
                VLANImportRowResult(
                    row=parsed.row, name=name, cidr=cidr, status="error", error=parsed.error
                )
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
            vlan = existing
            if on_conflict == "skip":
                skipped += 1
                status_label = "skipped"
            else:
                for key, value in fields.items():
                    setattr(existing, key, value)
                updated += 1
                status_label = "updated"
        else:
            vlan = VLAN(**fields)
            session.add(vlan)
            await session.flush()
            by_name[values["name"].lower()] = vlan
            created += 1
            status_label = "created"

        # Attach the row's IP range to this VLAN, independent of the VLAN's
        # create/update/skip outcome, deduped by CIDR.
        if cidr:
            if cidr in existing_ranges:
                ranges_skipped += 1
            else:
                session.add(IPRange(cidr=cidr, vlan_id=vlan.id))
                existing_ranges.add(cidr)
                ranges_created += 1

        results.append(
            VLANImportRowResult(row=parsed.row, name=name, cidr=cidr, status=status_label)
        )

    await append_audit(
        session,
        action="vlan.imported",
        actor_id=current_user.id,
        actor_email=current_user.email,
        target_type="vlan",
        target_id=None,
        payload={
            "total": len(rows),
            "created": created,
            "updated": updated,
            "errors": errors,
            "ranges_created": ranges_created,
        },
    )
    await session.commit()
    return VLANImportReport(
        total=len(rows),
        created=created,
        updated=updated,
        skipped=skipped,
        errors=errors,
        ranges_created=ranges_created,
        ranges_skipped=ranges_skipped,
        results=results,
    )


@vlans_router.post("/import/preview", response_model=list[VlanImportPreviewRow])
async def import_preview_vlans(
    file: UploadFile = File(...),
    _: User = Depends(WriteDep),
    session: AsyncSession = Depends(get_session),
) -> list[VlanImportPreviewRow]:
    """Parse a VLAN upload and return its rows (with an exists flag and any parse
    error) without applying anything, so the user can pick which to import."""
    content = await file.read()
    if len(content) > MAX_IMPORT_BYTES:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "File too large (max 5 MB)"
        )
    try:
        rows = parse_vlan_file(content, file.filename or "")
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    existing = {n.lower() for n in (await session.execute(select(VLAN.name))).scalars().all()}
    preview: list[VlanImportPreviewRow] = []
    for parsed in rows:
        v = parsed.values
        name = v.get("name")
        preview.append(
            VlanImportPreviewRow(
                row=parsed.row,
                name=name,
                vlan_tag=int(v["tag"]) if "tag" in v else None,
                description=v.get("description"),
                cidr=v.get("cidr"),
                exists=bool(name) and name.lower() in existing,
                error=parsed.error,
            )
        )
    return preview


@vlans_router.post("/import/apply", response_model=VLANImportReport)
async def import_apply_vlans(
    payload: VlanImportApply,
    on_conflict: str = Query("update", pattern="^(update|skip)$"),
    current_user: User = Depends(WriteDep),
    session: AsyncSession = Depends(get_session),
) -> VLANImportReport:
    """Apply a chosen subset of a VLAN import preview: upsert VLANs by name and
    attach their IP ranges by CIDR (VLAN + ranges as one unit)."""
    by_name = {
        v.name.lower(): v for v in (await session.execute(select(VLAN))).scalars()
    }
    existing_ranges = {r.cidr for r in (await session.execute(select(IPRange))).scalars()}
    results: list[VLANImportRowResult] = []
    created = updated = skipped = errors = 0
    ranges_created = ranges_skipped = 0
    for idx, item in enumerate(payload.items, start=1):
        if not item.name.strip():
            errors += 1
            results.append(VLANImportRowResult(row=idx, status="error", error="Missing name"))
            continue
        if item.vlan_tag is not None and not (1 <= item.vlan_tag <= 4094):
            errors += 1
            results.append(
                VLANImportRowResult(
                    row=idx, name=item.name, cidr=item.cidr, status="error",
                    error=f"VLAN tag out of range (1-4094): '{item.vlan_tag}'",
                )
            )
            continue
        cidr: str | None = None
        if item.cidr:
            try:
                cidr = str(ipaddress.ip_network(item.cidr, strict=False))
            except ValueError:
                errors += 1
                results.append(
                    VLANImportRowResult(
                        row=idx, name=item.name, cidr=item.cidr, status="error",
                        error=f"Invalid CIDR '{item.cidr}'",
                    )
                )
                continue

        fields: dict[str, object] = {"name": item.name}
        if item.vlan_tag is not None:
            fields["vlan_tag"] = item.vlan_tag
        if item.description:
            fields["description"] = item.description
        existing = by_name.get(item.name.lower())
        if existing is not None:
            vlan = existing
            if on_conflict == "skip":
                skipped += 1
                status_label = "skipped"
            else:
                for key, value in fields.items():
                    setattr(existing, key, value)
                updated += 1
                status_label = "updated"
        else:
            vlan = VLAN(**fields)
            session.add(vlan)
            await session.flush()
            by_name[item.name.lower()] = vlan
            created += 1
            status_label = "created"

        if cidr:
            if cidr in existing_ranges:
                ranges_skipped += 1
            else:
                session.add(IPRange(cidr=cidr, vlan_id=vlan.id))
                existing_ranges.add(cidr)
                ranges_created += 1

        results.append(
            VLANImportRowResult(row=idx, name=item.name, cidr=cidr, status=status_label)
        )

    await append_audit(
        session,
        action="vlan.imported",
        actor_id=current_user.id,
        actor_email=current_user.email,
        target_type="vlan",
        target_id=None,
        payload={
            "total": len(payload.items),
            "created": created,
            "updated": updated,
            "errors": errors,
            "ranges_created": ranges_created,
        },
    )
    await session.commit()
    return VLANImportReport(
        total=len(payload.items),
        created=created,
        updated=updated,
        skipped=skipped,
        errors=errors,
        ranges_created=ranges_created,
        ranges_skipped=ranges_skipped,
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


@vlans_router.get("/sync/preview", response_model=list[VlanPreviewItem])
async def sync_preview_vlans(
    _: User = Depends(WriteDep),
    session: AsyncSession = Depends(get_session),
    source: InventorySource = Depends(get_inventory_source),
) -> list[VlanPreviewItem]:
    """Show what a NetBox VLAN sync would bring in, without applying it."""
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
    existing = {n.lower() for n in (await session.execute(select(VLAN.name))).scalars().all()}
    return [
        VlanPreviewItem(
            name=i.name,
            vlan_tag=i.tag,
            description=i.description,
            exists=i.name.lower() in existing,
        )
        for i in items
    ]


@vlans_router.post("/sync/apply", response_model=VlanSyncReport)
async def sync_apply_vlans(
    payload: VlanSyncApply,
    on_conflict: str = Query("update", pattern="^(update|skip)$"),
    current_user: User = Depends(WriteDep),
    session: AsyncSession = Depends(get_session),
) -> VlanSyncReport:
    """Apply a chosen subset of a VLAN sync preview, upserting by name."""
    by_name = {
        v.name.lower(): v for v in (await session.execute(select(VLAN))).scalars()
    }
    created = updated = skipped = errors = 0
    errors_detail: list[str] = []
    for item in payload.items:
        if item.vlan_tag is not None and not (1 <= item.vlan_tag <= 4094):
            errors += 1
            errors_detail.append(f"VLAN '{item.name}' has out-of-range tag {item.vlan_tag}")
            continue
        fields: dict[str, object] = {"name": item.name}
        if item.vlan_tag is not None:
            fields["vlan_tag"] = item.vlan_tag
        if item.description:
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
            "source": "netbox",
            "total": len(payload.items),
            "created": created,
            "updated": updated,
            "skipped": skipped,
            "errors": errors,
        },
    )
    await session.commit()
    return VlanSyncReport(
        source="netbox",
        total=len(payload.items),
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


@vlans_router.post("/bulk-create", response_model=BulkReport)
async def bulk_create_vlans(
    payload: VlanBulkCreate,
    current_user: User = Depends(WriteDep),
    session: AsyncSession = Depends(get_session),
) -> BulkReport:
    """Create many VLANs at once (assistant bulk add). Existing names are skipped;
    an out-of-range tag is reported per item. One audit entry records the batch."""
    by_name = {
        v.name.lower(): v for v in (await session.execute(select(VLAN))).scalars()
    }
    created = skipped = errors = 0
    errors_detail: list[str] = []
    for item in payload.items:
        if item.vlan_tag is not None and not (1 <= item.vlan_tag <= 4094):
            errors += 1
            errors_detail.append(f"VLAN '{item.name}' has out-of-range tag {item.vlan_tag}")
            continue
        if item.name.lower() in by_name:
            skipped += 1
            continue
        vlan = VLAN(name=item.name, vlan_tag=item.vlan_tag, description=item.description)
        session.add(vlan)
        await session.flush()
        by_name[item.name.lower()] = vlan
        created += 1
    await append_audit(
        session,
        action="vlan.bulk_created",
        actor_id=current_user.id,
        actor_email=current_user.email,
        target_type="vlan",
        target_id=None,
        payload={"total": len(payload.items), "created": created, "skipped": skipped},
    )
    await session.commit()
    return BulkReport(
        total=len(payload.items),
        succeeded=created,
        skipped=skipped,
        errors=errors,
        errors_detail=errors_detail[:50],
    )


@vlans_router.post("/bulk-delete", response_model=BulkReport)
async def bulk_delete_vlans(
    payload: VlanBulkDelete,
    current_user: User = Depends(WriteDep),
    session: AsyncSession = Depends(get_session),
) -> BulkReport:
    """Delete many VLANs by name at once (assistant bulk delete). A name with no
    matching VLAN is reported, not an error. One audit entry records the batch."""
    by_name = {
        v.name.lower(): v for v in (await session.execute(select(VLAN))).scalars()
    }
    deleted = 0
    not_found: list[str] = []
    for name in payload.names:
        # pop so a duplicate name in the same request is only deleted once.
        vlan = by_name.pop(name.lower(), None)
        if vlan is None:
            not_found.append(name)
            continue
        await session.delete(vlan)
        deleted += 1
    await append_audit(
        session,
        action="vlan.bulk_deleted",
        actor_id=current_user.id,
        actor_email=current_user.email,
        target_type="vlan",
        target_id=None,
        payload={"total": len(payload.names), "deleted": deleted, "not_found": not_found},
    )
    await session.commit()
    return BulkReport(
        total=len(payload.names),
        succeeded=deleted,
        skipped=len(not_found),
        errors=0,
        errors_detail=not_found[:50],
    )


@vlans_router.post("/bulk-update", response_model=BulkReport)
async def bulk_update_vlans(
    payload: VlanBulkUpdate,
    current_user: User = Depends(WriteDep),
    session: AsyncSession = Depends(get_session),
) -> BulkReport:
    """Apply the same field change to many VLANs by id (bulk edit). One audit
    entry records the batch."""
    fields: dict[str, object] = {}
    if payload.description is not None:
        fields["description"] = payload.description
    if not fields:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Provide at least one field to update."
        )
    updated = 0
    not_found: list[str] = []
    for vlan_id in payload.ids:
        vlan = await session.get(VLAN, vlan_id)
        if vlan is None:
            not_found.append(str(vlan_id))
            continue
        for key, value in fields.items():
            setattr(vlan, key, value)
        updated += 1
    await append_audit(
        session,
        action="vlan.bulk_updated",
        actor_id=current_user.id,
        actor_email=current_user.email,
        target_type="vlan",
        target_id=None,
        payload={
            "total": len(payload.ids),
            "updated": updated,
            "fields": {k: audit_value(v) for k, v in fields.items()},
        },
    )
    await session.commit()
    return BulkReport(
        total=len(payload.ids),
        succeeded=updated,
        skipped=len(not_found),
        errors=0,
        errors_detail=not_found[:50],
    )


# IP ranges
ip_ranges_router = APIRouter(prefix="/ip-ranges", tags=["inventory"])


@ip_ranges_router.post("/sync", response_model=IPRangeSyncReport)
async def sync_ip_ranges(
    on_conflict: str = Query("update", pattern="^(update|skip)$"),
    current_user: User = Depends(WriteDep),
    session: AsyncSession = Depends(get_session),
    source: InventorySource = Depends(get_inventory_source),
) -> IPRangeSyncReport:
    """Pull IP ranges (prefixes) from the configured source (NetBox) and upsert
    them by CIDR, attaching each to its VLAN by name when present. Gated by the
    same toggle as VLANs (ranges travel with them). Audited as ip_range.synced."""
    if source.name == "none":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No inventory source is configured.")
    eff = await effective_settings(session)
    if not eff.netbox_import_vlans:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "VLAN and range import from NetBox is disabled."
        )
    try:
        items = await source.fetch_ranges()
    except Exception as exc:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, f"Inventory source unavailable: {exc}"
        ) from exc

    vlan_by_name = {
        v.name.lower(): v.id for v in (await session.execute(select(VLAN))).scalars()
    }
    by_cidr = {r.cidr: r for r in (await session.execute(select(IPRange))).scalars()}

    created = updated = skipped = errors = 0
    errors_detail: list[str] = []
    for item in items:
        try:
            cidr = str(ipaddress.ip_network(item.cidr, strict=False))
        except ValueError:
            errors += 1
            errors_detail.append(f"Invalid CIDR '{item.cidr}'")
            continue
        # An unknown VLAN name imports the range unassigned rather than failing.
        vlan_id = vlan_by_name.get(item.vlan_name.lower()) if item.vlan_name else None
        existing = by_cidr.get(cidr)
        if existing is not None:
            if on_conflict == "skip":
                skipped += 1
                continue
            if vlan_id is not None:
                existing.vlan_id = vlan_id
            if item.description:
                existing.description = item.description
            updated += 1
        else:
            ip_range = IPRange(cidr=cidr, vlan_id=vlan_id, description=item.description)
            session.add(ip_range)
            await session.flush()
            by_cidr[cidr] = ip_range
            created += 1

    await append_audit(
        session,
        action="ip_range.synced",
        actor_id=current_user.id,
        actor_email=current_user.email,
        target_type="ip_range",
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
    return IPRangeSyncReport(
        source=source.name,
        total=len(items),
        created=created,
        updated=updated,
        skipped=skipped,
        errors=errors,
        errors_detail=errors_detail[:50],
    )


@ip_ranges_router.get("/sync/preview", response_model=list[IPRangePreviewItem])
async def sync_preview_ip_ranges(
    _: User = Depends(WriteDep),
    session: AsyncSession = Depends(get_session),
    source: InventorySource = Depends(get_inventory_source),
) -> list[IPRangePreviewItem]:
    """Show what a NetBox range sync would bring in, without applying it."""
    if source.name == "none":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No inventory source is configured.")
    eff = await effective_settings(session)
    if not eff.netbox_import_vlans:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "VLAN and range import from NetBox is disabled."
        )
    try:
        items = await source.fetch_ranges()
    except Exception as exc:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, f"Inventory source unavailable: {exc}"
        ) from exc
    existing = set((await session.execute(select(IPRange.cidr))).scalars().all())
    preview: list[IPRangePreviewItem] = []
    for item in items:
        try:
            cidr = str(ipaddress.ip_network(item.cidr, strict=False))
        except ValueError:
            continue
        preview.append(
            IPRangePreviewItem(
                cidr=cidr,
                vlan_name=item.vlan_name,
                description=item.description,
                exists=cidr in existing,
            )
        )
    return preview


@ip_ranges_router.post("/sync/apply", response_model=IPRangeSyncReport)
async def sync_apply_ip_ranges(
    payload: IPRangeSyncApply,
    on_conflict: str = Query("update", pattern="^(update|skip)$"),
    current_user: User = Depends(WriteDep),
    session: AsyncSession = Depends(get_session),
) -> IPRangeSyncReport:
    """Apply a chosen subset of a range sync preview, upserting by CIDR and
    attaching each to its VLAN by name."""
    vlan_by_name = {
        v.name.lower(): v.id for v in (await session.execute(select(VLAN))).scalars()
    }
    by_cidr = {r.cidr: r for r in (await session.execute(select(IPRange))).scalars()}
    created = updated = skipped = errors = 0
    errors_detail: list[str] = []
    for item in payload.items:
        try:
            cidr = str(ipaddress.ip_network(item.cidr, strict=False))
        except ValueError:
            errors += 1
            errors_detail.append(f"Invalid CIDR '{item.cidr}'")
            continue
        vlan_id = vlan_by_name.get(item.vlan_name.lower()) if item.vlan_name else None
        existing = by_cidr.get(cidr)
        if existing is not None:
            if on_conflict == "skip":
                skipped += 1
                continue
            if vlan_id is not None:
                existing.vlan_id = vlan_id
            if item.description:
                existing.description = item.description
            updated += 1
        else:
            ip_range = IPRange(cidr=cidr, vlan_id=vlan_id, description=item.description)
            session.add(ip_range)
            await session.flush()
            by_cidr[cidr] = ip_range
            created += 1
    await append_audit(
        session,
        action="ip_range.synced",
        actor_id=current_user.id,
        actor_email=current_user.email,
        target_type="ip_range",
        target_id=None,
        payload={
            "source": "netbox",
            "total": len(payload.items),
            "created": created,
            "updated": updated,
            "skipped": skipped,
            "errors": errors,
        },
    )
    await session.commit()
    return IPRangeSyncReport(
        source="netbox",
        total=len(payload.items),
        created=created,
        updated=updated,
        skipped=skipped,
        errors=errors,
        errors_detail=errors_detail[:50],
    )


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


@ip_ranges_router.post("/bulk-create", response_model=BulkReport)
async def bulk_create_ip_ranges(
    payload: IPRangeBulkCreate,
    current_user: User = Depends(WriteDep),
    session: AsyncSession = Depends(get_session),
) -> BulkReport:
    """Create many IP ranges at once (assistant bulk add). CIDRs already present
    are skipped; an invalid CIDR or unknown VLAN is reported per item. One audit
    entry records the batch."""
    vlan_by_name = {
        v.name.lower(): v.id for v in (await session.execute(select(VLAN))).scalars()
    }
    existing = {r.cidr for r in (await session.execute(select(IPRange))).scalars()}
    created = skipped = errors = 0
    errors_detail: list[str] = []
    for item in payload.items:
        try:
            cidr = str(ipaddress.ip_network(item.cidr, strict=False))
        except ValueError:
            errors += 1
            errors_detail.append(f"Invalid CIDR '{item.cidr}'")
            continue
        vlan_id = None
        if item.vlan_name:
            vlan_id = vlan_by_name.get(item.vlan_name.lower())
            if vlan_id is None:
                errors += 1
                errors_detail.append(f"VLAN '{item.vlan_name}' not found")
                continue
        if cidr in existing:
            skipped += 1
            continue
        session.add(IPRange(cidr=cidr, vlan_id=vlan_id, description=item.description))
        existing.add(cidr)
        created += 1
    await append_audit(
        session,
        action="ip_range.bulk_created",
        actor_id=current_user.id,
        actor_email=current_user.email,
        target_type="ip_range",
        target_id=None,
        payload={"total": len(payload.items), "created": created, "skipped": skipped},
    )
    await session.commit()
    return BulkReport(
        total=len(payload.items),
        succeeded=created,
        skipped=skipped,
        errors=errors,
        errors_detail=errors_detail[:50],
    )


@ip_ranges_router.post("/bulk-delete", response_model=BulkReport)
async def bulk_delete_ip_ranges(
    payload: IPRangeBulkDelete,
    current_user: User = Depends(WriteDep),
    session: AsyncSession = Depends(get_session),
) -> BulkReport:
    """Delete many IP ranges by CIDR at once (assistant bulk delete). All ranges
    matching a given CIDR are removed; a CIDR with no match is reported. One audit
    entry records the batch."""
    deleted = 0
    not_found: list[str] = []
    for raw in payload.cidrs:
        try:
            cidr = str(ipaddress.ip_network(raw, strict=False))
        except ValueError:
            not_found.append(raw)
            continue
        rows = (
            await session.execute(select(IPRange).where(IPRange.cidr == cidr))
        ).scalars().all()
        if not rows:
            not_found.append(raw)
            continue
        for row in rows:
            await session.delete(row)
            deleted += 1
    await append_audit(
        session,
        action="ip_range.bulk_deleted",
        actor_id=current_user.id,
        actor_email=current_user.email,
        target_type="ip_range",
        target_id=None,
        payload={"total": len(payload.cidrs), "deleted": deleted, "not_found": not_found},
    )
    await session.commit()
    return BulkReport(
        total=len(payload.cidrs),
        succeeded=deleted,
        skipped=len(not_found),
        errors=0,
        errors_detail=not_found[:50],
    )


@ip_ranges_router.post("/bulk-update", response_model=BulkReport)
async def bulk_update_ip_ranges(
    payload: IPRangeBulkUpdate,
    current_user: User = Depends(WriteDep),
    session: AsyncSession = Depends(get_session),
) -> BulkReport:
    """Apply the same field changes to many IP ranges by id (bulk edit), e.g.
    assign a batch of ranges to a VLAN. One audit entry records the batch."""
    fields: dict[str, object] = {}
    if payload.vlan_id is not None:
        fields["vlan_id"] = payload.vlan_id
    if payload.description is not None:
        fields["description"] = payload.description
    if not fields:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Provide at least one field to update."
        )
    if payload.vlan_id is not None and await session.get(VLAN, payload.vlan_id) is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Referenced VLAN does not exist")

    updated = 0
    not_found: list[str] = []
    for range_id in payload.ids:
        ip_range = await session.get(IPRange, range_id)
        if ip_range is None:
            not_found.append(str(range_id))
            continue
        for key, value in fields.items():
            setattr(ip_range, key, value)
        updated += 1
    await append_audit(
        session,
        action="ip_range.bulk_updated",
        actor_id=current_user.id,
        actor_email=current_user.email,
        target_type="ip_range",
        target_id=None,
        payload={
            "total": len(payload.ids),
            "updated": updated,
            "fields": {k: audit_value(v) for k, v in fields.items()},
        },
    )
    await session.commit()
    return BulkReport(
        total=len(payload.ids),
        succeeded=updated,
        skipped=len(not_found),
        errors=0,
        errors_detail=not_found[:50],
    )


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


@assets_router.post("/import/preview", response_model=list[AssetImportPreviewRow])
async def import_preview_assets(
    file: UploadFile = File(...),
    _: User = Depends(WriteDep),
    session: AsyncSession = Depends(get_session),
) -> list[AssetImportPreviewRow]:
    """Parse an upload and return its rows (with an exists flag and any per-row
    parse error) without applying anything, so the user can pick which to import."""
    content = await file.read()
    if len(content) > MAX_IMPORT_BYTES:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "File too large (max 5 MB)"
        )
    try:
        rows = parse_asset_file(content, file.filename or "")
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    existing = set((await session.execute(select(Asset.ip))).scalars().all())
    preview: list[AssetImportPreviewRow] = []
    for parsed in rows:
        v = parsed.values
        ip = v.get("ip")
        preview.append(
            AssetImportPreviewRow(
                row=parsed.row,
                ip=ip,
                hostname=v.get("hostname"),
                vlan=v.get("vlan"),
                owner=v.get("owner"),
                criticality=v.get("criticality"),
                data_sensitivity=v.get("data_sensitivity"),
                description=v.get("description"),
                exists=bool(ip) and ip in existing,
                error=parsed.error,
            )
        )
    return preview


@assets_router.post("/import/apply", response_model=AssetImportReport)
async def import_apply_assets(
    payload: AssetImportApply,
    on_conflict: str = Query("update", pattern="^(update|skip)$"),
    current_user: User = Depends(WriteDep),
    session: AsyncSession = Depends(get_session),
) -> AssetImportReport:
    """Apply a chosen subset of an import preview, resolving VLAN names and owner
    emails and upserting by IP. An unknown reference fails just that row."""
    vlan_by_name = {
        v.name.lower(): v.id for v in (await session.execute(select(VLAN))).scalars()
    }
    user_by_email = {
        u.email.lower(): u.id for u in (await session.execute(select(User))).scalars()
    }
    results: list[AssetImportRowResult] = []
    created = updated = skipped = errors = 0
    for idx, item in enumerate(payload.items, start=1):
        try:
            ipaddress.ip_address(item.ip)
        except ValueError:
            errors += 1
            results.append(
                AssetImportRowResult(row=idx, ip=item.ip, status="error", error="Invalid IP")
            )
            continue
        fields: dict[str, object] = {}
        if item.hostname:
            fields["hostname"] = item.hostname
        if item.vlan:
            vlan_id = vlan_by_name.get(item.vlan.lower())
            if vlan_id is None:
                errors += 1
                results.append(
                    AssetImportRowResult(
                        row=idx, ip=item.ip, status="error",
                        error=f"Unknown VLAN '{item.vlan}'",
                    )
                )
                continue
            fields["vlan_id"] = vlan_id
        if item.owner:
            owner_id = user_by_email.get(item.owner.lower())
            if owner_id is None:
                errors += 1
                results.append(
                    AssetImportRowResult(
                        row=idx, ip=item.ip, status="error",
                        error=f"Unknown owner '{item.owner}'",
                    )
                )
                continue
            fields["owner_id"] = owner_id
        if item.criticality is not None:
            fields["criticality"] = item.criticality
        if item.data_sensitivity is not None:
            fields["data_sensitivity"] = item.data_sensitivity
        if item.description:
            fields["description"] = item.description
        outcome = await upsert_asset(session, item.ip, fields, on_conflict)
        if outcome == "created":
            created += 1
        elif outcome == "updated":
            updated += 1
        else:
            skipped += 1
        results.append(AssetImportRowResult(row=idx, ip=item.ip, status=outcome))
    await append_audit(
        session,
        action="asset.imported",
        actor_id=current_user.id,
        actor_email=current_user.email,
        target_type="asset",
        target_id=None,
        payload={
            "total": len(payload.items),
            "created": created,
            "updated": updated,
            "skipped": skipped,
            "errors": errors,
        },
    )
    await session.commit()
    return AssetImportReport(
        total=len(payload.items),
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


@assets_router.get("/sync/preview", response_model=list[AssetPreviewItem])
async def sync_preview_assets(
    _: User = Depends(WriteDep),
    session: AsyncSession = Depends(get_session),
    source: InventorySource = Depends(get_inventory_source),
) -> list[AssetPreviewItem]:
    """Show what a NetBox asset sync would bring in, without applying anything, so
    the staging UI can let the user select rows and set attributes first."""
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
    existing = set(
        (await session.execute(select(Asset.ip))).scalars().all()
    )
    preview: list[AssetPreviewItem] = []
    for item in items:
        try:
            ipaddress.ip_address(item.ip)
        except ValueError:
            continue  # invalid IPs are simply not offered
        preview.append(
            AssetPreviewItem(ip=item.ip, hostname=item.hostname, exists=item.ip in existing)
        )
    return preview


@assets_router.post("/sync/apply", response_model=AssetSyncReport)
async def sync_apply_assets(
    payload: AssetSyncApply,
    on_conflict: str = Query("update", pattern="^(update|skip)$"),
    current_user: User = Depends(WriteDep),
    session: AsyncSession = Depends(get_session),
) -> AssetSyncReport:
    """Apply a chosen subset of a sync preview, with attributes (criticality,
    owner, ...) set in the staging UI. Upserts by IP; one asset.synced audit."""
    # Validate every referenced VLAN/owner once before touching anything.
    for vlan_id in {i.vlan_id for i in payload.items if i.vlan_id}:
        if await session.get(VLAN, vlan_id) is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Referenced VLAN does not exist")
    for owner_id in {i.owner_id for i in payload.items if i.owner_id}:
        if await session.get(User, owner_id) is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Referenced owner does not exist")

    created = updated = skipped = errors = 0
    errors_detail: list[str] = []
    for item in payload.items:
        try:
            ipaddress.ip_address(item.ip)
        except ValueError:
            errors += 1
            errors_detail.append(f"Invalid IP '{item.ip}'")
            continue
        fields: dict[str, object] = {}
        if item.hostname:
            fields["hostname"] = item.hostname
        if item.criticality is not None:
            fields["criticality"] = item.criticality
        if item.data_sensitivity is not None:
            fields["data_sensitivity"] = item.data_sensitivity
        if item.owner_id is not None:
            fields["owner_id"] = item.owner_id
        if item.vlan_id is not None:
            fields["vlan_id"] = item.vlan_id
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
            "source": "netbox",
            "total": len(payload.items),
            "created": created,
            "updated": updated,
            "skipped": skipped,
            "errors": errors,
        },
    )
    await session.commit()
    return AssetSyncReport(
        source="netbox",
        total=len(payload.items),
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


@assets_router.post("/bulk-update", response_model=BulkReport)
async def bulk_update_assets(
    payload: AssetBulkUpdate,
    current_user: User = Depends(WriteDep),
    session: AsyncSession = Depends(get_session),
) -> BulkReport:
    """Apply the same field changes to many assets by IP (bulk edit). Only the
    fields set in the request are changed; an IP with no matching asset is
    reported. One audit entry records the batch."""
    fields: dict[str, object] = {}
    if payload.criticality is not None:
        fields["criticality"] = payload.criticality
    if payload.data_sensitivity is not None:
        fields["data_sensitivity"] = payload.data_sensitivity
    if payload.owner_id is not None:
        fields["owner_id"] = payload.owner_id
    if payload.vlan_id is not None:
        fields["vlan_id"] = payload.vlan_id
    if not fields:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Provide at least one field to update."
        )
    await _validate_asset_refs(session, payload.vlan_id, payload.owner_id)

    updated = 0
    not_found: list[str] = []
    for ip in payload.ips:
        asset = (
            await session.execute(select(Asset).where(Asset.ip == ip))
        ).scalars().first()
        if asset is None:
            not_found.append(ip)
            continue
        for key, value in fields.items():
            setattr(asset, key, value)
        asset.updated_at = _utcnow()
        updated += 1
    await append_audit(
        session,
        action="asset.bulk_updated",
        actor_id=current_user.id,
        actor_email=current_user.email,
        target_type="asset",
        target_id=None,
        payload={
            "total": len(payload.ips),
            "updated": updated,
            "fields": {k: audit_value(v) for k, v in fields.items()},
        },
    )
    await session.commit()
    return BulkReport(
        total=len(payload.ips),
        succeeded=updated,
        skipped=len(not_found),
        errors=0,
        errors_detail=not_found[:50],
    )
