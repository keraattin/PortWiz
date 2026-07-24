"""One-click auditor evidence package.

Bundles everything an auditor needs for a scan profile into a single payload:
the profile, its scan runs, the current confirmed-open exposure, the confirmed
changes, and a fresh integrity check over the immutable audit log. Generating a
package is itself audited (chain of custody).
"""

from __future__ import annotations

import datetime as dt
import uuid

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.audit import append_audit, verify_chain
from ...core.db import get_session
from ...models.audit import AuditEvent
from ...models.change import ChangeEvent, PortState
from ...models.cve import CVEFinding
from ...models.scan import ScanProfile, ScanRun
from ...models.user import User, UserRole
from ...schemas.audit import ChainVerification
from ...schemas.change import ChangeEventRead
from ...schemas.cve import CVEFindingRead
from ...schemas.evidence import EvidencePackage, OpenPort
from ...schemas.scan import ScanProfileRead, ScanRunRead
from ..deps import require_roles

router = APIRouter(prefix="/evidence", tags=["evidence"])

ReadDep = require_roles(UserRole.admin, UserRole.auditor)


def _utcnow() -> dt.datetime:
    return dt.datetime.now(tz=dt.timezone.utc)


async def build_evidence(
    session: AsyncSession, profile: ScanProfile, generated_by: str
) -> EvidencePackage:
    runs = (
        await session.execute(
            select(ScanRun)
            .where(ScanRun.scan_profile_id == profile.id)
            .order_by(ScanRun.created_at.desc())
            .limit(100)
        )
    ).scalars().all()

    changes = (
        await session.execute(
            select(ChangeEvent)
            .where(ChangeEvent.scan_profile_id == profile.id)
            .order_by(ChangeEvent.detected_at.desc())
        )
    ).scalars().all()

    states = (
        await session.execute(
            select(PortState)
            .where(
                PortState.scan_profile_id == profile.id,
                PortState.confirmed_state == "open",
            )
            .order_by(PortState.ip, PortState.port)
        )
    ).scalars().all()

    # Known vulnerabilities for exactly the profile's confirmed-open exposure.
    # Findings are keyed by (ip, port); intersect them with the open states so
    # the package documents CVEs for what is actually exposed, most severe first.
    open_pairs = {(s.ip, s.port) for s in states}
    open_ips = {s.ip for s in states}
    cve_findings: list[CVEFinding] = []
    if open_ips:
        cve_rows = (
            await session.execute(
                select(CVEFinding)
                .where(CVEFinding.ip.in_(open_ips))
                .order_by(func.coalesce(CVEFinding.cvss, 0).desc(), CVEFinding.cve_id)
            )
        ).scalars().all()
        cve_findings = [c for c in cve_rows if (c.ip, c.port) in open_pairs]

    # A fresh integrity check over the whole immutable audit log. The individual
    # events are intentionally not bundled: the report documents exposure and
    # changes, and this attests the tamper-evident log behind them is intact.
    ok, broken_seq = await verify_chain(session)
    total = (
        await session.execute(select(func.count()).select_from(AuditEvent))
    ).scalar_one()

    return EvidencePackage(
        generated_at=_utcnow(),
        generated_by=generated_by,
        profile=ScanProfileRead.model_validate(profile),
        chain_verification=ChainVerification(ok=ok, broken_seq=broken_seq, total=total),
        current_open_ports=[
            OpenPort(
                ip=s.ip,
                port=s.port,
                protocol=s.protocol,
                service=s.confirmed_service,
                version=s.confirmed_version,
                last_seen_open_at=s.last_seen_open_at,
            )
            for s in states
        ],
        cve_findings=[CVEFindingRead.model_validate(c) for c in cve_findings],
        scan_runs=[ScanRunRead.model_validate(r) for r in runs],
        changes=[ChangeEventRead.model_validate(c) for c in changes],
    )


@router.get("/scan-profiles/{profile_id}", response_model=EvidencePackage)
async def evidence_for_profile(
    profile_id: uuid.UUID,
    current_user: User = Depends(ReadDep),
    session: AsyncSession = Depends(get_session),
) -> EvidencePackage:
    profile = await session.get(ScanProfile, profile_id)
    if profile is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Scan profile not found")

    package = await build_evidence(session, profile, current_user.email)

    # Chain of custody: record who exported evidence and when.
    await append_audit(
        session,
        action="evidence.exported",
        actor_id=current_user.id,
        actor_email=current_user.email,
        target_type="scan_profile",
        target_id=str(profile_id),
        payload={
            "format": "json",
            "runs": len(package.scan_runs),
            "changes": len(package.changes),
            "cves": len(package.cve_findings),
        },
    )
    await session.commit()
    return package


@router.get("/scan-profiles/{profile_id}/pdf")
async def evidence_for_profile_pdf(
    profile_id: uuid.UUID,
    current_user: User = Depends(ReadDep),
    session: AsyncSession = Depends(get_session),
) -> Response:
    # Imported lazily so the app does not require reportlab unless a PDF is built.
    from ...core.evidence_pdf import render_evidence_pdf

    profile = await session.get(ScanProfile, profile_id)
    if profile is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Scan profile not found")

    package = await build_evidence(session, profile, current_user.email)
    pdf_bytes = render_evidence_pdf(package)

    await append_audit(
        session,
        action="evidence.exported",
        actor_id=current_user.id,
        actor_email=current_user.email,
        target_type="scan_profile",
        target_id=str(profile_id),
        payload={
            "format": "pdf",
            "runs": len(package.scan_runs),
            "changes": len(package.changes),
            "cves": len(package.cve_findings),
        },
    )
    await session.commit()

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="portwiz-evidence-{profile_id}.pdf"'
        },
    )
