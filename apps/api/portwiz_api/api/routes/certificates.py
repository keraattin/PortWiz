"""TLS certificate inventory (observability).

The current leaf certificate for each TLS port seen during scans, with an expiry
status. Read-only and available to any authenticated user; it drives the
certificate list UI and pairs with the expiry-alert scheduler job.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.app_settings import effective_settings
from ...core.cert_monitor import current_certificates
from ...core.db import get_session
from ...models.asset import Asset
from ...models.user import User
from ...schemas.certificate import CertificateRead
from ..deps import get_current_user

router = APIRouter(prefix="/certificates", tags=["certificates"])


@router.get("", response_model=list[CertificateRead])
async def list_certificates(
    status: str | None = None,
    ip: str | None = None,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[CertificateRead]:
    """Current TLS certificates, soonest-expiry first. Filter by ``status``
    (expired|expiring|valid) or ``ip``. The warning window that classifies
    "expiring" follows the configured ``cert_expiry_warn_days``."""
    s = await effective_settings(session)
    certs = await current_certificates(session, warn_days=s.cert_expiry_warn_days)
    if status is not None:
        certs = [c for c in certs if c.status == status]
    if ip is not None:
        certs = [c for c in certs if c.ip == ip]

    # Enrich with hostname from the matching asset (by IP), in one query.
    hostmap: dict[str, str] = {}
    ips = {c.ip for c in certs}
    if ips:
        rows = (
            await session.execute(
                select(Asset.ip, Asset.hostname).where(Asset.ip.in_(ips))
            )
        ).all()
        hostmap = {row_ip: hn for row_ip, hn in rows if hn}

    return [
        CertificateRead(
            ip=c.ip,
            port=c.port,
            protocol=c.protocol,
            asset_id=c.asset_id,
            hostname=hostmap.get(c.ip),
            subject_cn=c.subject_cn,
            issuer=c.issuer,
            sans=c.sans,
            not_before=c.not_before,
            not_after=c.not_after,
            self_signed=c.self_signed,
            serial=c.serial,
            sig_alg=c.sig_alg,
            days_to_expiry=c.days_to_expiry,
            status=c.status,
        )
        for c in certs
    ]
