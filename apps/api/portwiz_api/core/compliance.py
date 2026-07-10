"""Compliance cadence tracking.

Each framework requires periodic scanning at a known interval. A framework
"template" pairs that required interval with a recommended cron schedule, so
tagging a scan profile with a framework can pre-fill a compliant schedule and we
can flag when a profile's own schedule would under-scan the requirement.

For every framework-tagged profile we report two things:
- **cadence status**: does the most recent successful scan still fall inside the
  required interval (compliant / due_soon / overdue / never)?
- **schedule adequacy**: does the profile's cron fire often enough to keep it
  compliant going forward, or is the configured schedule too sparse (or absent)?

PCI-DSS additionally requires external scans by an Approved Scanning Vendor; an
internal PortWiz scan does not satisfy that, so the status flags it.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.scan import ComplianceFramework, ScanProfile, ScanRun, ScanRunStatus, ScanSource


@dataclass(frozen=True)
class FrameworkTemplate:
    """A framework's required scan cadence plus a schedule that satisfies it."""

    framework: str
    label: str
    cadence_days: int  # scan at least this often to stay compliant
    recommended_cron: str  # a schedule comfortably inside cadence_days
    recommended_label: str  # human name for that schedule (e.g. "monthly")
    requires_external_asv: bool  # an internal scan alone does not satisfy it
    description: str


# Per-framework templates. Cadences are simplified, sensible defaults; real
# programs may tighten them. Recommended crons are chosen to fire comfortably
# inside the required interval (e.g. monthly for PCI's 90-day window, since a
# strict quarterly schedule can drift to 92 days and breach it).
FRAMEWORK_TEMPLATES: dict[str, FrameworkTemplate] = {
    ComplianceFramework.pci.value: FrameworkTemplate(
        framework=ComplianceFramework.pci.value,
        label="PCI-DSS",
        cadence_days=90,
        recommended_cron="0 3 1 * *",  # monthly, 03:00 on the 1st
        recommended_label="monthly",
        requires_external_asv=True,
        description=(
            "Quarterly internal scanning. PCI-DSS also requires quarterly external "
            "scans by an Approved Scanning Vendor (ASV); an internal PortWiz scan "
            "does not satisfy that requirement."
        ),
    ),
    ComplianceFramework.hipaa.value: FrameworkTemplate(
        framework=ComplianceFramework.hipaa.value,
        label="HIPAA",
        cadence_days=180,
        recommended_cron="0 3 1 */3 *",  # quarterly
        recommended_label="quarterly",
        requires_external_asv=False,
        description="Periodic vulnerability scanning; semi-annual is common practice.",
    ),
    ComplianceFramework.soc2.value: FrameworkTemplate(
        framework=ComplianceFramework.soc2.value,
        label="SOC 2",
        cadence_days=365,
        recommended_cron="0 3 1 */3 *",  # quarterly
        recommended_label="quarterly",
        requires_external_asv=False,
        description="Annual scanning at minimum; quarterly demonstrates stronger monitoring.",
    ),
    ComplianceFramework.iso27001.value: FrameworkTemplate(
        framework=ComplianceFramework.iso27001.value,
        label="ISO 27001",
        cadence_days=365,
        recommended_cron="0 3 1 */3 *",  # quarterly
        recommended_label="quarterly",
        requires_external_asv=False,
        description="Risk-based cadence; quarterly is a common baseline for A.8.9 drift.",
    ),
    ComplianceFramework.nist.value: FrameworkTemplate(
        framework=ComplianceFramework.nist.value,
        label="NIST",
        cadence_days=365,
        recommended_cron="0 3 1 */3 *",  # quarterly
        recommended_label="quarterly",
        requires_external_asv=False,
        description="Risk-based continuous monitoring (CM-8/SI-4); quarterly baseline.",
    ),
}

# Back-compat: the required interval per framework, derived from the templates.
FRAMEWORK_CADENCE_DAYS: dict[str, int] = {
    fw: tpl.cadence_days for fw, tpl in FRAMEWORK_TEMPLATES.items()
}

# A run in one of these states means a scan actually happened.
_SCANNED_STATES = [ScanRunStatus.completed, ScanRunStatus.partial]

# Fixed base and horizon for sampling cron fire times. The base is a leap year so
# a two-year-plus horizon captures the worst-case gap (including Feb) for monthly,
# quarterly and annual schedules without depending on the current date.
_CRON_SAMPLE_BASE = dt.datetime(2024, 1, 1, tzinfo=dt.timezone.utc)
_CRON_SAMPLE_HORIZON_DAYS = 800


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


def max_cron_gap_days(cron_expr: str | None) -> int | None:
    """Largest gap (in days) between consecutive fires of a cron schedule.

    Samples fire times over a fixed multi-year window so the result is
    deterministic. Returns None for an absent or invalid expression. Used to
    decide whether a schedule fires often enough to keep a profile compliant.
    """
    from croniter import croniter

    if not cron_expr or not croniter.is_valid(cron_expr):
        return None
    horizon = _CRON_SAMPLE_BASE + dt.timedelta(days=_CRON_SAMPLE_HORIZON_DAYS)
    itr = croniter(cron_expr, _CRON_SAMPLE_BASE)
    prev = itr.get_next(dt.datetime)
    max_gap = 0.0
    while True:
        nxt = itr.get_next(dt.datetime)
        if nxt > horizon:
            break
        max_gap = max(max_gap, (nxt - prev).total_seconds() / 86400)
        prev = nxt
    return int(round(max_gap)) if max_gap > 0 else None


def cron_meets_cadence(cron_expr: str | None, cadence_days: int) -> bool:
    """True if the schedule fires at least once per required interval."""
    gap = max_cron_gap_days(cron_expr)
    return gap is not None and gap <= cadence_days


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
        template = FRAMEWORK_TEMPLATES[framework]
        cadence_days = template.cadence_days
        # PCI external-ASV requirement: internal scans do not satisfy it.
        asv_satisfied = (
            not template.requires_external_asv
            or profile.scan_source == ScanSource.external_asv
        )
        schedule_gap_days = max_cron_gap_days(profile.cron)
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
                "cron": profile.cron,
                "recommended_cron": template.recommended_cron,
                # A schedule is adequate only if it exists and fires within cadence.
                "schedule_ok": schedule_gap_days is not None
                and schedule_gap_days <= cadence_days,
                "schedule_gap_days": schedule_gap_days,
            }
        )
    return items
