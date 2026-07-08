"""CVE findings: re-check discovered services against a CVE source and list them."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.audit import append_audit
from ...core.cve import CVESource, NullCVESource, get_cve_source, recheck_cves
from ...core.db import get_session
from ...models.cve import CVEFinding
from ...models.user import User, UserRole
from ...schemas.cve import CVEFindingRead, CVERecheckResult
from ..deps import get_current_user, require_roles

router = APIRouter(prefix="/cve", tags=["cve"])

WriteDep = require_roles(UserRole.admin, UserRole.operator)


@router.post("/recheck", response_model=CVERecheckResult)
async def recheck(
    limit: int = Query(default=25, ge=1, le=100),
    current_user: User = Depends(WriteDep),
    session: AsyncSession = Depends(get_session),
    source: CVESource = Depends(get_cve_source),
) -> CVERecheckResult:
    """Look up CVEs for the current open ports (latest observation with a version)
    and replace each port's findings. Bounded by ``limit`` for rate limits."""
    if isinstance(source, NullCVESource):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "CVE enrichment is not configured")
    result = await recheck_cves(session, source, limit)
    await append_audit(
        session,
        action="cve.rechecked",
        actor_id=current_user.id,
        actor_email=current_user.email,
        target_type="cve",
        target_id="*",
        payload={"source": source.name, **result},
    )
    await session.commit()
    return CVERecheckResult(**result)


@router.get("/findings", response_model=list[CVEFindingRead])
async def list_findings(
    severity: str | None = None,
    ip: str | None = None,
    min_cvss: float | None = Query(default=None, ge=0, le=10),
    limit: int = Query(default=200, ge=1, le=500),
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[CVEFinding]:
    # Highest CVSS first (coalesce so unscored findings sort last on either DB).
    query = select(CVEFinding).order_by(
        func.coalesce(CVEFinding.cvss, 0).desc(), CVEFinding.detected_at.desc()
    )
    if severity is not None:
        query = query.where(CVEFinding.severity == severity)
    if ip is not None:
        query = query.where(CVEFinding.ip == ip)
    if min_cvss is not None:
        query = query.where(CVEFinding.cvss >= min_cvss)
    result = await session.execute(query.limit(limit))
    return list(result.scalars().all())
