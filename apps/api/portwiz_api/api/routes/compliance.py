"""Compliance cadence reporting.

Read-only for any authenticated user: shows, per framework-tagged scan profile,
whether its latest successful scan still falls inside the framework's required
interval.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.compliance import FRAMEWORK_TEMPLATES, compliance_status
from ...core.db import get_session
from ...models.user import User
from ...schemas.compliance import ComplianceStatusItem, FrameworkTemplateRead
from ..deps import get_current_user

router = APIRouter(prefix="/compliance", tags=["compliance"])


@router.get("/frameworks", response_model=list[FrameworkTemplateRead])
async def list_frameworks(
    _: User = Depends(get_current_user),
) -> list[FrameworkTemplateRead]:
    """Catalog of supported frameworks with their required cadence and a
    recommended schedule, so the scan-profile form can apply a compliant one."""
    return [FrameworkTemplateRead(**vars(tpl)) for tpl in FRAMEWORK_TEMPLATES.values()]


@router.get("/status", response_model=list[ComplianceStatusItem])
async def get_compliance_status(
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    return await compliance_status(session)
