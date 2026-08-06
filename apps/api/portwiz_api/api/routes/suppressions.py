"""Port false-positive suppressions.

Mark a detected port as a false positive so it is hidden from the current-open
-ports view and never raises a change again; remove the suppression to restore
it. Reads are open to any authenticated user; create/delete require admin or
operator. Suppressions are global across scan profiles.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.audit import append_audit
from ...core.db import get_session
from ...models.change import PortSuppression
from ...models.user import User, UserRole
from ...schemas.suppression import SuppressionCreate, SuppressionRead
from ..deps import get_current_user, require_roles

router = APIRouter(prefix="/suppressions", tags=["suppressions"])

WriteDep = require_roles(UserRole.admin, UserRole.operator)


@router.get("", response_model=list[SuppressionRead])
async def list_suppressions(
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[PortSuppression]:
    rows = (
        (
            await session.execute(
                select(PortSuppression).order_by(
                    PortSuppression.ip, PortSuppression.port, PortSuppression.protocol
                )
            )
        )
        .scalars()
        .all()
    )
    return list(rows)


@router.post("", response_model=SuppressionRead, status_code=status.HTTP_201_CREATED)
async def create_suppression(
    payload: SuppressionCreate,
    current_user: User = Depends(WriteDep),
    session: AsyncSession = Depends(get_session),
) -> PortSuppression:
    """Mark a (host, port) as a false positive. Idempotent: an already-suppressed
    port returns the existing suppression rather than erroring."""
    existing = (
        (
            await session.execute(
                select(PortSuppression).where(
                    PortSuppression.ip == payload.ip,
                    PortSuppression.port == payload.port,
                    PortSuppression.protocol == payload.protocol,
                )
            )
        )
        .scalars()
        .first()
    )
    if existing is not None:
        return existing

    supp = PortSuppression(
        ip=payload.ip,
        port=payload.port,
        protocol=payload.protocol,
        reason=payload.reason,
        created_by=current_user.id,
    )
    session.add(supp)
    await session.flush()
    await append_audit(
        session,
        action="port.suppressed",
        actor_id=current_user.id,
        actor_email=current_user.email,
        target_type="port_suppression",
        target_id=str(supp.id),
        payload={
            "target": f"{supp.ip}:{supp.port}/{supp.protocol}",
            "reason": supp.reason,
        },
    )
    await session.commit()
    await session.refresh(supp)
    return supp


@router.delete("/{suppression_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_suppression(
    suppression_id: uuid.UUID,
    current_user: User = Depends(WriteDep),
    session: AsyncSession = Depends(get_session),
) -> None:
    """Remove a suppression so the port is scanned and surfaced normally again."""
    supp = await session.get(PortSuppression, suppression_id)
    if supp is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Suppression not found")
    target = f"{supp.ip}:{supp.port}/{supp.protocol}"
    await session.delete(supp)
    await append_audit(
        session,
        action="port.unsuppressed",
        actor_id=current_user.id,
        actor_email=current_user.email,
        target_type="port_suppression",
        target_id=str(suppression_id),
        payload={"target": target},
    )
    await session.commit()
