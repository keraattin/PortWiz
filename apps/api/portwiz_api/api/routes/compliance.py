"""Compliance cadence reporting.

Read-only for any authenticated user: shows, per framework-tagged scan profile,
whether its latest successful scan still falls inside the framework's required
interval.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.compliance import compliance_status
from ...core.db import get_session
from ...models.user import User
from ...schemas.compliance import ComplianceStatusItem
from ..deps import get_current_user

router = APIRouter(prefix="/compliance", tags=["compliance"])


@router.get("/status", response_model=list[ComplianceStatusItem])
async def get_compliance_status(
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    return await compliance_status(session)
