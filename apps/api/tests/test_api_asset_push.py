"""API tests for NetBox writeback of discovered hosts (POST /assets/push-netbox).

A fake inventory source is injected via dependency override, so these run with
no NetBox instance.
"""

from __future__ import annotations


class FakeSource:
    name = "netbox"

    def __init__(self) -> None:
        self.pushed: list[str] = []

    async def push_assets(self, assets):
        from portwiz_api.core.inventory_source import PushResult

        self.pushed = [a.ip for a in assets]
        return PushResult(created=len(assets))


def _use_source(src) -> None:
    from portwiz_api.core.inventory_source import get_inventory_source
    from portwiz_api.main import app

    app.dependency_overrides[get_inventory_source] = lambda: src


async def _seed(db, *assets) -> None:
    from portwiz_api.models.asset import Asset, Criticality

    async with db() as session:
        for ip, hostname, discovered in assets:
            session.add(
                Asset(
                    ip=ip,
                    hostname=hostname,
                    criticality=Criticality.low,
                    discovered=discovered,
                )
            )
        await session.commit()


async def test_push_requires_auth(client) -> None:
    assert (await client.post("/api/v1/assets/push-netbox")).status_code == 401


async def test_push_not_configured_returns_400(client, admin_headers) -> None:
    # Hermetic env disables NetBox, so get_inventory_source yields NullSource.
    resp = await client.post("/api/v1/assets/push-netbox", headers=admin_headers)
    assert resp.status_code == 400


async def test_push_only_discovered_assets(client, admin_headers, db) -> None:
    await _seed(db, ("10.9.0.1", "disc-1", True), ("10.9.0.2", "manual", False))
    src = FakeSource()
    _use_source(src)

    resp = await client.post("/api/v1/assets/push-netbox", headers=admin_headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["source"] == "netbox"
    assert body["total"] == 1
    assert body["created"] == 1
    # Only the discovered host is written back; the manual one is left alone.
    assert src.pushed == ["10.9.0.1"]


async def test_push_is_audited(client, admin_headers, db) -> None:
    await _seed(db, ("10.9.0.3", None, True))
    _use_source(FakeSource())
    await client.post("/api/v1/assets/push-netbox", headers=admin_headers)
    audit = (await client.get("/api/v1/audit", headers=admin_headers)).json()
    assert any(e["action"] == "asset.pushed" for e in audit["events"])
