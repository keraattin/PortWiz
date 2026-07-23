"""Current open-port state (observability).

Surfaces the confirmed-open ports from the change-detection state machine, so you
can see which hosts currently expose which ports, not just the change events.
Read-only and available to any authenticated user.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.db import get_session
from ...models.asset import Asset
from ...models.change import PortState
from ...models.user import User
from ...schemas.ports import OpenPortRead
from ..deps import get_current_user

router = APIRouter(prefix="/ports", tags=["ports"])


@router.get("", response_model=list[OpenPortRead])
async def list_open_ports(
    ip: str | None = None,
    port: int | None = None,
    protocol: str | None = None,
    service: str | None = None,
    asset_id: uuid.UUID | None = None,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[OpenPortRead]:
    """Every port confirmed open right now, one row per (ip, port, protocol),
    joined to its asset. This is current state, independent of change events."""
    query = (
        select(PortState, Asset)
        .outerjoin(Asset, Asset.ip == PortState.ip)
        .where(PortState.confirmed_state == "open")
        .order_by(
            PortState.ip,
            PortState.port,
            PortState.protocol,
            PortState.last_seen_open_at.desc(),
        )
    )
    if ip is not None:
        query = query.where(PortState.ip == ip)
    if port is not None:
        query = query.where(PortState.port == port)
    if protocol is not None:
        query = query.where(PortState.protocol == protocol)
    if service is not None:
        query = query.where(PortState.confirmed_service == service)
    if asset_id is not None:
        query = query.where(Asset.id == asset_id)

    rows = (await session.execute(query)).all()
    seen: set[tuple[str, int, str]] = set()
    out: list[OpenPortRead] = []
    for state, asset in rows:
        key = (state.ip, state.port, state.protocol)
        if key in seen:  # a host can sit in several scan profiles; keep the freshest
            continue
        seen.add(key)
        out.append(
            OpenPortRead(
                ip=state.ip,
                port=state.port,
                protocol=state.protocol,
                service=state.confirmed_service,
                version=state.confirmed_version,
                last_seen_open_at=state.last_seen_open_at,
                asset_id=asset.id if asset else None,
                hostname=asset.hostname if asset else None,
                criticality=(
                    getattr(asset.criticality, "value", asset.criticality) if asset else None
                ),
            )
        )
    return out
