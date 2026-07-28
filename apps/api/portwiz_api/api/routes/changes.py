"""Confirmed change events: listing, viewing, and status updates.

Reads are available to any authenticated user; status changes (acknowledge,
resolve) require admin or operator.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.audit import append_audit
from ...core.db import get_session
from ...models.change import ChangeEvent
from ...models.user import User, UserRole
from ...schemas.change import ChangeEventRead, ChangeEventUpdate
from ..deps import get_current_user, require_roles

router = APIRouter(prefix="/changes", tags=["changes"])

WriteDep = require_roles(UserRole.admin, UserRole.operator)


@router.get("", response_model=list[ChangeEventRead])
async def list_changes(
    scan_profile_id: uuid.UUID | None = None,
    change_type: str | None = None,
    status_filter: str | None = Query(default=None, alias="status"),
    ip: str | None = None,
    port: int | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[ChangeEvent]:
    query = select(ChangeEvent).order_by(ChangeEvent.detected_at.desc()).limit(limit)
    if scan_profile_id is not None:
        query = query.where(ChangeEvent.scan_profile_id == scan_profile_id)
    if change_type is not None:
        query = query.where(ChangeEvent.change_type == change_type)
    if status_filter is not None:
        query = query.where(ChangeEvent.status == status_filter)
    # ip/port scope the change history for a single host or port, powering the
    # per-host and per-port timelines.
    if ip is not None:
        query = query.where(ChangeEvent.ip == ip)
    if port is not None:
        query = query.where(ChangeEvent.port == port)
    result = await session.execute(query)
    return list(result.scalars().all())


@router.get("/{change_id}", response_model=ChangeEventRead)
async def get_change(
    change_id: uuid.UUID,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ChangeEvent:
    change = await session.get(ChangeEvent, change_id)
    if change is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Change event not found")
    return change


@router.patch("/{change_id}", response_model=ChangeEventRead)
async def update_change_status(
    change_id: uuid.UUID,
    payload: ChangeEventUpdate,
    current_user: User = Depends(WriteDep),
    session: AsyncSession = Depends(get_session),
) -> ChangeEvent:
    change = await session.get(ChangeEvent, change_id)
    if change is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Change event not found")
    old_status = change.status
    change.status = payload.status
    await append_audit(
        session,
        action="change.status_updated",
        actor_id=current_user.id,
        actor_email=current_user.email,
        target_type="change_event",
        target_id=str(change.id),
        payload={
            "target": f"{change.ip}:{change.port}/{change.protocol}",
            "status": {"old": old_status, "new": payload.status},
        },
    )
    await session.commit()
    await session.refresh(change)
    return change
