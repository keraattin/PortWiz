"""Update check: report whether a newer PortWiz release is available."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi import status as http_status
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.app_settings import effective_settings
from ...core.audit import append_audit
from ...core.db import get_session
from ...core.update_check import get_update_status, request_apply
from ...models.user import User, UserRole
from ...schemas.update import UpdateStatusRead
from ..deps import require_roles

router = APIRouter(prefix="/update", tags=["update"])

AdminDep = require_roles(UserRole.admin)


@router.get("/status", response_model=UpdateStatusRead)
async def status(
    _: User = Depends(AdminDep),
    session: AsyncSession = Depends(get_session),
) -> UpdateStatusRead:
    """Cached update status (disabled installs report enabled=false)."""
    return UpdateStatusRead(**vars(await get_update_status(await effective_settings(session))))


@router.post("/check", response_model=UpdateStatusRead)
async def check(
    _: User = Depends(AdminDep),
    session: AsyncSession = Depends(get_session),
) -> UpdateStatusRead:
    """Force a fresh check against GitHub, bypassing the cache."""
    return UpdateStatusRead(
        **vars(await get_update_status(await effective_settings(session), force=True))
    )


@router.post("/apply", status_code=http_status.HTTP_202_ACCEPTED)
async def apply(
    current_user: User = Depends(AdminDep),
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    """Record a one-click update request for the updater sidecar to apply. The
    API never touches Docker itself; the sidecar (with the socket) does the pull
    and restart. 400 when no updater is deployed."""
    eff = await effective_settings(session)
    if not eff.update_apply_enabled:
        raise HTTPException(
            http_status.HTTP_400_BAD_REQUEST,
            "One-click update is not available (no updater sidecar deployed).",
        )
    await request_apply(session)
    await append_audit(
        session,
        action="update.requested",
        actor_id=current_user.id,
        actor_email=current_user.email,
        target_type="update",
        target_id="*",
        payload={"from_version": eff.app_version or "unknown"},
    )
    await session.commit()
    return {"status": "requested"}
