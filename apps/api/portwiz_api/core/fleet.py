"""Agent fleet health and segment coverage.

A PortWiz deployment can run many agents, one per network segment. This module
computes each agent's live status and, for multi-segment fleets, where coverage
is missing: a segment that has scan profiles but no online agent to run them is a
blind spot (scheduled runs will queue with nothing to claim them).

The online rule matches the dashboard: an agent is online if it heartbeat within
its window (the global ``agent_online_seconds``, or the agent's own override for
a fragile segment).
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.agent import Agent
from ..models.scan import ScanProfile
from .app_settings import effective_settings

# Agent status values (also used by the dashboard counts).
ONLINE = "online"
OFFLINE = "offline"
NEVER = "never"
DISABLED = "disabled"


def _utcnow() -> dt.datetime:
    return dt.datetime.now(tz=dt.timezone.utc)


def _aware(value: dt.datetime) -> dt.datetime:
    # SQLite drops tzinfo on DateTime(timezone=True); stored values are UTC.
    return value if value.tzinfo is not None else value.replace(tzinfo=dt.timezone.utc)


def agent_status(agent: Agent, now: dt.datetime, global_online_seconds: int) -> str:
    """Live status of one agent: disabled, never (seen), online, or offline."""
    if not agent.enabled:
        return DISABLED
    if agent.last_seen_at is None:
        return NEVER
    window = dt.timedelta(seconds=agent.online_seconds_override or global_online_seconds)
    return ONLINE if (now - _aware(agent.last_seen_at)) < window else OFFLINE


@dataclass
class SegmentCoverage:
    segment: str | None  # None = the unsegmented pool
    agents_total: int
    agents_online: int
    profiles: int  # enabled scan profiles routed to this segment
    covered: bool  # at least one online agent serves it


async def fleet_summary(session: AsyncSession, now: dt.datetime | None = None) -> dict:
    """Fleet-wide status counts plus per-segment coverage and coverage gaps.

    A *gap* is a segment with one or more enabled scan profiles but no online
    agent: its scheduled runs have nothing to claim them.
    """
    now = _utcnow() if now is None else _aware(now)
    eff = await effective_settings(session)
    window = eff.agent_online_seconds

    agents = (await session.execute(select(Agent))).scalars().all()
    statuses = [agent_status(a, now, window) for a in agents]
    totals = {ONLINE: 0, OFFLINE: 0, NEVER: 0, DISABLED: 0}
    for s in statuses:
        totals[s] += 1

    # Enabled scan profiles grouped by the segment they route to.
    profile_rows = (
        await session.execute(
            select(ScanProfile.segment, func.count())
            .where(ScanProfile.enabled.is_(True))
            .group_by(ScanProfile.segment)
        )
    ).all()
    profiles_by_segment: dict[str | None, int] = {seg: n for seg, n in profile_rows}

    # Every segment that either an agent serves or a profile targets.
    segments = {a.segment for a in agents} | set(profiles_by_segment)
    coverage: list[SegmentCoverage] = []
    for seg in segments:
        in_seg = [(a, st) for a, st in zip(agents, statuses, strict=True) if a.segment == seg]
        online = sum(1 for _, st in in_seg if st == ONLINE)
        coverage.append(
            SegmentCoverage(
                segment=seg,
                agents_total=len(in_seg),
                agents_online=online,
                profiles=profiles_by_segment.get(seg, 0),
                covered=online > 0,
            )
        )
    # Stable order: gaps and busiest segments first, then by name; None last.
    coverage.sort(key=lambda c: (c.covered, -c.profiles, c.segment is None, c.segment or ""))
    gaps = [c for c in coverage if c.profiles > 0 and c.agents_online == 0]

    return {
        "agents_total": len(agents),
        "agents_online": totals[ONLINE],
        "agents_offline": totals[OFFLINE],
        "agents_never_seen": totals[NEVER],
        "agents_disabled": totals[DISABLED],
        "segments": coverage,
        "gaps": gaps,
    }
