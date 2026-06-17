"""Compliance cadence tracking.

Each framework requires periodic scanning at a known interval. For every scan
profile tagged with a framework, we compute whether its most recent successful
scan still falls inside that interval, so an auditor can see at a glance which
assets are scanned on schedule and which are overdue.

PCI-DSS additionally requires external scans by an Approved Scanning Vendor; an
internal PortWiz scan does not satisfy that, so the status flags it.
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.scan import ComplianceFramework, ScanProfile, ScanRun, ScanRunStatus, ScanSource

# Required scan interval per framework, in days. Simplified, sensible defaults;
# real programs may tighten these.
FRAMEWORK_CADENCE_DAYS: dict[str, int] = {
    ComplianceFramework.pci.value: 90,
    ComplianceFramework.hipaa.value: 180,
    ComplianceFramework.soc2.value: 365,
    ComplianceFramework.iso27001.value: 365,
    ComplianceFramework.nist.value: 365,
}

# A run in one of these states means a scan actually happened.
_SCANNED_STATES = [ScanRunStatus.completed, ScanRunStatus.partial]


def _utcnow() -> dt.datetime:
    return dt.datetime.now(tz=dt.timezone.utc)


def _aware(value: dt.datetime) -> dt.datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=dt.timezone.utc)


def cadence_status(cadence_days: int, days_since: int | None) -> str:
    if days_since is None:
        return "never"
    if days_since > cadence_days:
        return "overdue"
    if days_since > cadence_days * 0.85:
        return "due_soon"
    return "compliant"


async def compliance_status(
    session: AsyncSession, now: dt.datetime | None = None
) -> list[dict]:
    """Per-profile cadence status for every framework-tagged scan profile."""
    now = _utcnow() if now is None else _aware(now)
    profiles = (
        await session.execute(
            select(ScanProfile)
            .where(ScanProfile.compliance_framework.is_not(None))
            .order_by(ScanProfile.name)
        )
    ).scalars().all()

    items: list[dict] = []
    for profile in profiles:
        last_scan_at = (
            await session.execute(
                select(func.max(ScanRun.finished_at)).where(
                    ScanRun.scan_profile_id == profile.id,
                    ScanRun.status.in_(_SCANNED_STATES),
                    ScanRun.finished_at.is_not(None),
                )
            )
        ).scalar_one_or_none()

        days_since = (
            (now - _aware(last_scan_at)).days if last_scan_at is not None else None
        )
        framework = ComplianceFramework(profile.compliance_framework).value
        cadence_days = FRAMEWORK_CADENCE_DAYS[framework]
        # PCI external-ASV requirement: internal scans do not satisfy it.
        asv_satisfied = (
            framework != ComplianceFramework.pci.value
            or profile.scan_source == ScanSource.external_asv
        )
        items.append(
            {
                "profile_id": profile.id,
                "profile_name": profile.name,
                "framework": framework,
                "cadence_days": cadence_days,
                "last_scan_at": last_scan_at,
                "days_since": days_since,
                "status": cadence_status(cadence_days, days_since),
                "scan_source": ScanSource(profile.scan_source).value,
                "asv_satisfied": asv_satisfied,
            }
        )
    return items
