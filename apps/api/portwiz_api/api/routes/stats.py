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

from ...core.db import get_session
from ...models.agent import Agent
from ...models.asset import VLAN, Asset
from ...models.change import ChangeEvent
from ...models.scan import ScanRun
from ...models.task import Task
from ...models.user import User
from ...schemas.stats import DashboardStats
from ..deps import get_current_user

router = APIRouter(prefix="/stats", tags=["stats"])

# An agent that has heartbeat within this window counts as online.
_ONLINE_WINDOW = dt.timedelta(minutes=2)


def _is_online(last_seen: dt.datetime | None, now: dt.datetime) -> bool:
    if last_seen is None:
        return False
    if last_seen.tzinfo is None:  # SQLite drops tzinfo; stored values are UTC
        last_seen = last_seen.replace(tzinfo=dt.timezone.utc)
    return (now - last_seen) < _ONLINE_WINDOW


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
    agents_online = sum(1 for a in agents if _is_online(a.last_seen_at, now))

    last_run = (
        await session.execute(select(ScanRun).order_by(ScanRun.created_at.desc()).limit(1))
    ).scalar_one_or_none()
    last_scan_at = (last_run.finished_at or last_run.started_at) if last_run else None

    return DashboardStats(
        assets=assets,
        vlans=vlans,
        agents_total=len(agents),
        agents_online=agents_online,
        open_changes=open_changes,
        open_tasks=open_tasks,
        pending_runs=pending_runs,
        last_scan_at=last_scan_at,
    )
