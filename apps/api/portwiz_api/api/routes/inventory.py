"""Asset inventory CRUD: VLANs, IP ranges, and assets.

Reads are available to any authenticated user; writes require admin or operator.
Every create/update/delete is recorded in the immutable audit log.
"""

from __future__ import annotations

import datetime as dt
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.audit import append_audit
from ...core.db import get_session
from ...models.asset import IPRange, VLAN, Asset
from ...models.user import User, UserRole
from ...schemas.asset import (
    AssetCreate,
    AssetRead,
    AssetUpdate,
    IPRangeCreate,
    IPRangeRead,
    IPRangeUpdate,
    VLANCreate,
    VLANRead,
    VLANUpdate,
)
from ..deps import get_current_user, require_roles

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
    for key, value in changes.items():
        setattr(vlan, key, value)
    await append_audit(
        session,
        action="vlan.updated",
        actor_id=current_user.id,
        actor_email=current_user.email,
        target_type="vlan",
        target_id=str(vlan.id),
        payload={"changes": list(changes.keys())},
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
    for key, value in changes.items():
        setattr(ip_range, key, value)
    await append_audit(
        session,
        action="ip_range.updated",
        actor_id=current_user.id,
        actor_email=current_user.email,
        target_type="ip_range",
        target_id=str(ip_range.id),
        payload={"changes": list(changes.keys())},
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
        payload={"ip": asset.ip, "criticality": asset.criticality, "owner_id": str(asset.owner_id) if asset.owner_id else None},
    )
    await session.commit()
    await session.refresh(asset)
    return asset


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
        payload={"changes": list(changes.keys())},
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
