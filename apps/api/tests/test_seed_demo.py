"""Tests for the demo data seeding helper."""

from __future__ import annotations


async def _count(db, model) -> int:
    from sqlalchemy import func, select

    async with db() as session:
        return (await session.execute(select(func.count()).select_from(model))).scalar_one()


async def test_seed_demo_populates_and_is_idempotent(db) -> None:
    from portwiz_api.models.agent import Agent
    from portwiz_api.models.asset import VLAN, Asset
    from portwiz_api.models.change import ChangeEvent
    from portwiz_api.models.task import Task
    from portwiz_api.seed_demo import seed_demo

    await seed_demo(db)

    assert await _count(db, Agent) == 6
    assert await _count(db, VLAN) == 3
    assert await _count(db, Asset) == 5
    assert await _count(db, ChangeEvent) == 4
    assert await _count(db, Task) == 2

    # Running again is a no-op (guarded by the marker VLAN), so counts hold.
    await seed_demo(db)
    assert await _count(db, Agent) == 6
    assert await _count(db, VLAN) == 3


async def test_seed_demo_covers_every_agent_state(db) -> None:
    from sqlalchemy import select

    from portwiz_api.models.agent import Agent
    from portwiz_api.seed_demo import seed_demo

    await seed_demo(db)

    async with db() as session:
        agents = (await session.execute(select(Agent))).scalars().all()

    # One disabled, one never-seen, and some with reported metadata.
    assert any(not a.enabled for a in agents)
    assert any(a.last_seen_at is None for a in agents)
    assert any(a.version and a.platform and a.last_ip for a in agents)
