"""TLS certificate expiry monitoring.

Certificates captured during scans land on the observation (``Observation.cert_*``,
see :mod:`portwiz_api.api.routes.ingest`). This module summarizes them into a
current per-(ip, port) view with an expiry status, and fans an alert out over the
configured notification channels for the ones that are expired or close to it.
"""

from __future__ import annotations

import datetime as dt
import logging
import uuid
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.scan import Observation

logger = logging.getLogger("portwiz.cert_monitor")


def _utcnow() -> dt.datetime:
    return dt.datetime.now(tz=dt.timezone.utc)


def _aware(value: dt.datetime) -> dt.datetime:
    # SQLite drops tzinfo on DateTime(timezone=True); assume UTC for naive values.
    return value if value.tzinfo is not None else value.replace(tzinfo=dt.timezone.utc)


@dataclass
class CertStatus:
    """A port's current certificate plus its expiry classification."""

    ip: str
    port: int
    protocol: str
    asset_id: uuid.UUID | None
    subject_cn: str | None
    issuer: str | None
    sans: list[str] | None
    not_before: dt.datetime | None
    not_after: dt.datetime | None
    self_signed: bool | None
    serial: str | None
    sig_alg: str | None
    days_to_expiry: int | None
    status: str  # "expired" | "expiring" | "valid"


def _classify(
    not_after: dt.datetime | None, now: dt.datetime, warn_days: int
) -> tuple[int | None, str]:
    if not_after is None:
        return None, "valid"
    na = _aware(not_after)
    days = (na - now).days
    if na <= now:
        return days, "expired"
    if na <= now + dt.timedelta(days=warn_days):
        return days, "expiring"
    return days, "valid"


async def current_certificates(
    session: AsyncSession,
    now: dt.datetime | None = None,
    warn_days: int = 30,
) -> list[CertStatus]:
    """The most recently observed TLS certificate for each (ip, port, protocol).

    Only ports whose latest cert-bearing observation carries a ``not_after`` are
    returned. A renewed certificate supersedes the old one (the newest
    observation wins); a port that stops presenting a certificate keeps its last
    known one until a newer observation replaces it. Sorted soonest-expiry first.
    """
    now = _utcnow() if now is None else _aware(now)
    # Latest cert-bearing observation per (ip, port, protocol). Group-by + join
    # (rather than DISTINCT ON) so the query runs on both PostgreSQL and SQLite.
    latest = (
        select(
            Observation.ip,
            Observation.port,
            Observation.protocol,
            func.max(Observation.ts).label("mts"),
        )
        .where(Observation.cert_not_after.is_not(None))
        .group_by(Observation.ip, Observation.port, Observation.protocol)
        .subquery()
    )
    rows = (
        (
            await session.execute(
                select(Observation).join(
                    latest,
                    (Observation.ip == latest.c.ip)
                    & (Observation.port == latest.c.port)
                    & (Observation.protocol == latest.c.protocol)
                    & (Observation.ts == latest.c.mts),
                )
            )
        )
        .scalars()
        .all()
    )

    out: list[CertStatus] = []
    for o in rows:
        days, status = _classify(o.cert_not_after, now, warn_days)
        out.append(
            CertStatus(
                ip=o.ip,
                port=o.port,
                protocol=o.protocol,
                asset_id=o.asset_id,
                subject_cn=o.cert_subject_cn,
                issuer=o.cert_issuer,
                sans=o.cert_sans,
                not_before=o.cert_not_before,
                not_after=o.cert_not_after,
                self_signed=o.cert_self_signed,
                serial=o.cert_serial,
                sig_alg=o.cert_sig_alg,
                days_to_expiry=days,
                status=status,
            )
        )
    out.sort(key=lambda c: _aware(c.not_after) if c.not_after else now)
    return out


def expiring_certificates(certs: list[CertStatus]) -> list[CertStatus]:
    """The subset that is expired or within the warning window."""
    return [c for c in certs if c.status in ("expired", "expiring")]


def _severity(cert: CertStatus) -> str:
    return "high" if cert.status == "expired" else "medium"


def build_cert_expiry_message(certs: list[CertStatus]) -> tuple[str, str]:
    expired = sum(1 for c in certs if c.status == "expired")
    expiring = len(certs) - expired
    subject = (
        f"PortWiz: {expired} expired and {expiring} expiring TLS "
        f"certificate{'s' if len(certs) != 1 else ''}"
    )
    lines = ["PortWiz found TLS certificates that need attention:", ""]
    for c in certs:
        name = c.subject_cn or c.issuer or "unknown"
        until = c.not_after.date().isoformat() if c.not_after else "unknown"
        if c.status == "expired":
            state = f"EXPIRED {abs(c.days_to_expiry or 0)}d ago"
        else:
            state = f"expires in {c.days_to_expiry}d"
        lines.append(f"- [{state}] {c.ip}:{c.port} {name} (valid until {until})")
    return subject, "\n".join(lines)


async def notify_cert_expiry(certs: list[CertStatus], settings) -> int:
    """Alert on expired/expiring certificates over every configured channel.

    Unlike change notifications, certificate alerts are estate-wide, so only each
    channel's minimum-severity rule applies (no scan-profile scoping): an expired
    cert is high severity, an expiring one medium. Best-effort per channel; a
    failing channel is logged and skipped, never raised.
    """
    from .notifications import build_channels, meets_min_severity

    if not certs:
        return 0
    channels = build_channels(settings)
    if not channels:
        return 0
    recipients = list(settings.notification_recipients)
    dispatched = 0
    for ch in channels:
        selected = [c for c in certs if meets_min_severity(_severity(c), ch.min_severity)]
        if not selected:
            continue
        subject, body = build_cert_expiry_message(selected)
        try:
            await ch.notifier.send(subject, body, recipients)
            dispatched += 1
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "cert expiry notification via %s failed: %s",
                type(ch.notifier).__name__,
                exc,
            )
    return dispatched
