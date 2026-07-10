"""Dashboard overview: lightweight counts for the landing page.

Available to any authenticated user. Counts only, no secrets. The agent
online-window and last-scan time are computed in Python so the SQLite test
backend (which drops tzinfo) and PostgreSQL behave identically.
"""

from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.app_settings import effective_settings
from ...core.compliance import compliance_status
from ...core.db import get_session
from ...core.fleet import DISABLED, NEVER, OFFLINE, ONLINE, agent_status
from ...models.agent import Agent
from ...models.asset import VLAN, Asset, Criticality
from ...models.change import ChangeEvent
from ...models.scan import ScanRun, ScanRunStatus
from ...models.task import Task
from ...models.user import User
from ...schemas.stats import DashboardCharts, DashboardStats, Slice, TimePoint
from ..deps import get_current_user

router = APIRouter(prefix="/stats", tags=["stats"])

# Fixed category orders so charts stay stable and zero-fill empty buckets.
_CHANGE_TYPES = ["opened", "closed", "service_changed", "version_changed"]
_CRITICALITIES = [c.value for c in Criticality]
_RUN_STATUSES = [s.value for s in ScanRunStatus]
_COMPLIANCE_STATUSES = ["compliant", "due_soon", "overdue", "never"]
_CHART_DAYS = 30


def _aware(value: dt.datetime) -> dt.datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=dt.timezone.utc)


def _slices(counts: dict[str, int], order: list[str]) -> list[Slice]:
    """Zero-filled slices in a fixed order, then any unexpected extras."""
    out = [Slice(name=k, value=counts.get(k, 0)) for k in order]
    extras = sorted(k for k in counts if k not in order)
    out.extend(Slice(name=k, value=counts[k]) for k in extras)
    return out


@router.get("", response_model=DashboardStats)
async def get_stats(
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> DashboardStats:
    async def count(model, *where) -> int:
        query = select(func.count()).select_from(model)
        for clause in where:
            query = query.where(clause)
        return (await session.execute(query)).scalar_one()

    assets = await count(Asset)
    vlans = await count(VLAN)
    open_changes = await count(ChangeEvent, ChangeEvent.status == "open")
    open_tasks = await count(Task, Task.status.in_(["open", "in_progress"]))
    pending_runs = await count(ScanRun, ScanRun.status == "pending")

    agents = (await session.execute(select(Agent))).scalars().all()
    now = dt.datetime.now(tz=dt.timezone.utc)
    # Honour the admin-tunable online cut-off (and per-agent overrides) so the
    # dashboard agrees with the Agents page. Shared with the fleet view.
    eff = await effective_settings(session)
    counts = {ONLINE: 0, OFFLINE: 0, NEVER: 0, DISABLED: 0}
    for a in agents:
        counts[agent_status(a, now, eff.agent_online_seconds)] += 1
    agents_online = counts[ONLINE]
    agents_offline = counts[OFFLINE]
    agents_never_seen = counts[NEVER]
    agents_disabled = counts[DISABLED]

    last_run = (
        await session.execute(select(ScanRun).order_by(ScanRun.created_at.desc()).limit(1))
    ).scalar_one_or_none()
    last_scan_at = (last_run.finished_at or last_run.started_at) if last_run else None

    return DashboardStats(
        assets=assets,
        vlans=vlans,
        agents_total=len(agents),
        agents_online=agents_online,
        agents_offline=agents_offline,
        agents_never_seen=agents_never_seen,
        agents_disabled=agents_disabled,
        open_changes=open_changes,
        open_tasks=open_tasks,
        pending_runs=pending_runs,
        last_scan_at=last_scan_at,
    )


@router.get("/charts", response_model=DashboardCharts)
async def get_charts(
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> DashboardCharts:
    """Aggregated series for the dashboard charts. Counts only, no secrets.

    Grouping is done in Python over small result sets so the SQLite test
    backend and PostgreSQL agree (no date_trunc portability concerns).
    """

    async def grouped(col) -> dict[str, int]:
        rows = (await session.execute(select(col, func.count()).group_by(col))).all()
        counts: dict[str, int] = {}
        for value, n in rows:
            key = value.value if hasattr(value, "value") else str(value)
            counts[key] = counts.get(key, 0) + n
        return counts

    # Changes per day over the trailing window, zero-filled.
    now = dt.datetime.now(tz=dt.timezone.utc)
    start = (now - dt.timedelta(days=_CHART_DAYS - 1)).date()
    detected = (await session.execute(select(ChangeEvent.detected_at))).scalars().all()
    per_day: dict[str, int] = {}
    for value in detected:
        day = _aware(value).date()
        if day >= start:
            key = day.isoformat()
            per_day[key] = per_day.get(key, 0) + 1
    changes_by_day = [
        TimePoint(
            date=(start + dt.timedelta(days=i)).isoformat(),
            count=per_day.get((start + dt.timedelta(days=i)).isoformat(), 0),
        )
        for i in range(_CHART_DAYS)
    ]

    compliance = await compliance_status(session, now)
    compliance_counts: dict[str, int] = {}
    for item in compliance:
        compliance_counts[item["status"]] = compliance_counts.get(item["status"], 0) + 1

    return DashboardCharts(
        changes_by_day=changes_by_day,
        changes_by_type=_slices(await grouped(ChangeEvent.change_type), _CHANGE_TYPES),
        assets_by_criticality=_slices(await grouped(Asset.criticality), _CRITICALITIES),
        runs_by_status=_slices(await grouped(ScanRun.status), _RUN_STATUSES),
        compliance_by_status=_slices(compliance_counts, _COMPLIANCE_STATUSES),
    )
