"""Shared asset upsert, keyed by IP.

Used by the external-source sync (NetBox today). Bulk import has its own copy
for now; both converge on the same create-or-update-by-IP semantics.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.asset import Asset


async def upsert_asset(
    session: AsyncSession,
    ip: str,
    fields: dict[str, Any],
    on_conflict: str = "update",
) -> str:
    """Create or update an asset by IP. ``fields`` are already-resolved model
    attributes (hostname, vlan_id, description, ...). Returns one of
    ``created`` / ``updated`` / ``skipped``. The caller commits."""
    existing = (
        await session.execute(select(Asset).where(Asset.ip == ip))
    ).scalars().first()
    if existing is not None:
        if on_conflict == "skip":
            return "skipped"
        for key, value in fields.items():
            setattr(existing, key, value)
        existing.updated_at = dt.datetime.now(tz=dt.timezone.utc)
        return "updated"
    session.add(Asset(ip=ip, **fields))
    # Flush so a duplicate IP later in the same batch updates instead of inserting.
    await session.flush()
    return "created"
