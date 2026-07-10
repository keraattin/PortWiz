"""Tests for agent fleet status and segment coverage."""

from __future__ import annotations

import datetime as dt

from portwiz_api.core.fleet import DISABLED, NEVER, OFFLINE, ONLINE, agent_status
from portwiz_api.models.agent import Agent

_NOW = dt.datetime(2026, 7, 11, 12, 0, 0, tzinfo=dt.timezone.utc)


def _agent(**kw) -> Agent:
    kw.setdefault("name", "a")
    kw.setdefault("token_hash", "h")
    return Agent(**kw)


def test_agent_status_buckets() -> None:
    assert agent_status(_agent(enabled=False), _NOW, 120) == DISABLED
    assert agent_status(_agent(last_seen_at=None), _NOW, 120) == NEVER
    assert agent_status(_agent(last_seen_at=_NOW - dt.timedelta(seconds=30)), _NOW, 120) == ONLINE
    assert agent_status(_agent(last_seen_at=_NOW - dt.timedelta(seconds=300)), _NOW, 120) == OFFLINE


def test_agent_status_honours_override() -> None:
    # 5 minutes stale would be offline under the 120s global window...
    stale = _agent(last_seen_at=_NOW - dt.timedelta(seconds=300))
    assert agent_status(stale, _NOW, 120) == OFFLINE
    # ...but the agent's own wider window keeps it online (fragile segment).
    stale.online_seconds_override = 600
    assert agent_status(stale, _NOW, 120) == ONLINE


async def test_fleet_summary_coverage_and_gaps(db) -> None:
    from portwiz_api.core.fleet import fleet_summary
    from portwiz_api.models.scan import ScanProfile

    recent = _NOW - dt.timedelta(seconds=30)
    stale = _NOW - dt.timedelta(days=1)
    async with db() as session:
        session.add(Agent(name="a1", token_hash="h1", segment="a", last_seen_at=recent))  # online
        session.add(Agent(name="b1", token_hash="h2", segment="b", last_seen_at=stale))  # offline
        session.add(ScanProfile(name="pa", targets=["10.0.0.1"], segment="a"))
        session.add(ScanProfile(name="pb", targets=["10.0.0.2"], segment="b"))
        session.add(ScanProfile(name="pc", targets=["10.0.0.3"], segment="c"))  # no agent
        # A disabled profile does not create a coverage obligation.
        session.add(ScanProfile(name="pd", targets=["10.0.0.4"], segment="d", enabled=False))
        await session.commit()
        summary = await fleet_summary(session, now=_NOW)

    assert summary["agents_total"] == 2
    assert summary["agents_online"] == 1
    assert summary["agents_offline"] == 1
    by_seg = {s.segment: s for s in summary["segments"]}
    assert by_seg["a"].covered is True and by_seg["a"].agents_online == 1
    assert by_seg["b"].covered is False and by_seg["b"].profiles == 1
    # Gaps: enabled profiles with no online agent (b has an offline agent, c has none).
    gap_segs = {g.segment for g in summary["gaps"]}
    assert gap_segs == {"b", "c"}
    assert "d" not in gap_segs  # disabled profile -> no obligation


async def test_list_agents_includes_status(client, admin_headers) -> None:
    await client.post("/api/v1/agents", json={"name": "s1"}, headers=admin_headers)
    body = (await client.get("/api/v1/agents", headers=admin_headers)).json()
    assert body[0]["status"] == "never"  # enrolled but never seen


async def test_fleet_endpoint_reports_gap(client, admin_headers) -> None:
    # An agent in segment x, a profile in segment y with no agent -> y is a gap.
    await client.post("/api/v1/agents", json={"name": "fx", "segment": "x"}, headers=admin_headers)
    await client.post(
        "/api/v1/scan-profiles",
        json={"name": "py", "targets": ["10.0.0.9"], "segment": "y"},
        headers=admin_headers,
    )
    resp = await client.get("/api/v1/agents/fleet", headers=admin_headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["agents_total"] == 1
    assert "y" in {g["segment"] for g in body["gaps"]}


async def test_fleet_endpoint_requires_auth(client) -> None:
    assert (await client.get("/api/v1/agents/fleet")).status_code == 401
