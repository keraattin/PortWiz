"""CVE findings: re-check discovered services against a CVE source and list them."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.ai import AIProvider, get_ai_provider
from ...core.audit import append_audit
from ...core.cve import CVESource, NullCVESource, get_cve_source, import_nvd_feed, recheck_cves
from ...core.cve_ai import summarize_cves
from ...core.db import get_session
from ...models.cve import CVEFinding, CveRecord
from ...models.user import User, UserRole
from ...schemas.cve import CVEFindingRead, CVEImportReport, CVERecheckResult, CVESummary
from ..deps import get_current_user, require_roles
from .ai import ai_rate_limited

# NVD feeds are large; a gzipped per-year file is well under this.
MAX_FEED_BYTES = 100 * 1024 * 1024

logger = logging.getLogger("portwiz.cve")

router = APIRouter(prefix="/cve", tags=["cve"])

WriteDep = require_roles(UserRole.admin, UserRole.operator)


@router.post("/recheck", response_model=CVERecheckResult)
async def recheck(
    limit: int = Query(default=25, ge=1, le=100),
    current_user: User = Depends(WriteDep),
    session: AsyncSession = Depends(get_session),
    source: CVESource = Depends(get_cve_source),
) -> CVERecheckResult:
    """Look up CVEs for the current open ports with an identified service (latest
    observation carrying a product, service, or version), whether or not a change
    was detected, and replace each port's findings. Bounded by ``limit`` for rate
    limits."""
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


@router.post("/import", response_model=CVEImportReport)
async def import_feed(
    file: UploadFile = File(...),
    current_user: User = Depends(require_roles(UserRole.admin)),
    session: AsyncSession = Depends(get_session),
) -> CVEImportReport:
    """Upload an NVD 2.0 JSON feed (plain or .gz) into the offline CVE store, so
    enrichment works with no outbound access. Upserts by CVE id; audited."""
    content = await file.read()
    if len(content) > MAX_FEED_BYTES:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "File too large (max 100 MB)"
        )
    try:
        result = await import_nvd_feed(session, content)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc

    loaded = (await session.execute(select(func.count()).select_from(CveRecord))).scalar_one()
    await append_audit(
        session,
        action="cve.feed_imported",
        actor_id=current_user.id,
        actor_email=current_user.email,
        target_type="cve",
        target_id="*",
        payload={"filename": file.filename, "loaded": loaded, **result},
    )
    await session.commit()
    return CVEImportReport(total=result["total"], imported=result["imported"], loaded=loaded)


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


@router.post("/summary", response_model=CVESummary)
async def summary(
    ip: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    _: User = Depends(ai_rate_limited),
    provider: AIProvider = Depends(get_ai_provider),
    session: AsyncSession = Depends(get_session),
) -> CVESummary:
    """Plain-language, prioritised brief of the REAL stored CVE findings.

    The AI only summarises what a source already returned: it is handed the
    findings verbatim and its output is scrubbed of any CVE id not in that set,
    so it can never introduce an invented vulnerability.
    """
    if provider.name == "none":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "AI is not configured")

    query = select(CVEFinding).order_by(func.coalesce(CVEFinding.cvss, 0).desc())
    if ip is not None:
        query = query.where(CVEFinding.ip == ip)
    findings = list((await session.execute(query.limit(limit))).scalars().all())
    if not findings:
        # Nothing to brief: skip the (billable) AI call entirely.
        return CVESummary(provider=provider.name, count=0, summary="")

    try:
        text = await summarize_cves(provider, findings)
    except Exception as exc:  # external call boundary: never leak a 500
        logger.warning("CVE summary failed (%s): %s", provider.name, exc)
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, "AI provider unavailable"
        ) from exc
    return CVESummary(provider=provider.name, count=len(findings), summary=text)
