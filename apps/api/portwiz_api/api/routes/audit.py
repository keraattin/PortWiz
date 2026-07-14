"""Audit log viewing and integrity verification.

The audit log is the immutable, hash-chained record written from day one. These
endpoints expose it to auditors and admins (separation of duties: operators do
not read it) and let anyone with access verify the chain has not been tampered
with.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.audit import verify_chain
from ...core.db import get_session
from ...models.audit import AuditEvent
from ...models.user import User, UserRole
from ...schemas.audit import AuditPage, ChainVerification
from ..deps import require_roles

router = APIRouter(prefix="/audit", tags=["audit"])

ReadDep = require_roles(UserRole.admin, UserRole.auditor)


@router.get("", response_model=AuditPage)
async def list_audit(
    action: str | None = None,
    target_type: str | None = None,
    target_id: str | None = None,
    actor_email: str | None = None,
    limit: int = Query(default=50, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    _: User = Depends(ReadDep),
    session: AsyncSession = Depends(get_session),
) -> AuditPage:
    conditions = []
    if action is not None:
        conditions.append(AuditEvent.action == action)
    if target_type is not None:
        conditions.append(AuditEvent.target_type == target_type)
    if target_id is not None:
        conditions.append(AuditEvent.target_id == target_id)
    if actor_email is not None:
        conditions.append(AuditEvent.actor_email == actor_email)

    total = (
        await session.execute(
            select(func.count()).select_from(AuditEvent).where(*conditions)
        )
    ).scalar_one()

    rows = (
        await session.execute(
            select(AuditEvent)
            .where(*conditions)
            .order_by(AuditEvent.seq.desc())
            .limit(limit)
            .offset(offset)
        )
    ).scalars().all()

    return AuditPage(total=total, events=list(rows))


@router.get("/verify", response_model=ChainVerification)
async def verify_audit(
    _: User = Depends(ReadDep),
    session: AsyncSession = Depends(get_session),
) -> ChainVerification:
    ok, broken_seq = await verify_chain(session)
    total = (
        await session.execute(select(func.count()).select_from(AuditEvent))
    ).scalar_one()
    return ChainVerification(ok=ok, broken_seq=broken_seq, total=total)
