"""API tests for external inventory VLAN sync (POST /vlans/sync).

A fake inventory source is injected via dependency override, so these run with
no NetBox instance.
"""

from __future__ import annotations


class FakeSource:
    name = "netbox"

    def __init__(self, items) -> None:
        self._items = items

    async def fetch_vlans(self):
        return self._items

    async def verify(self):
        return True, "ok"


def _use_source(items):
    from portwiz_api.core.inventory_source import get_inventory_source
    from portwiz_api.main import app

    app.dependency_overrides[get_inventory_source] = lambda: FakeSource(items)


def _vlan(name, tag=None, description=None):
    from portwiz_api.core.inventory_source import SourceVlan

    return SourceVlan(name=name, tag=tag, description=description)


async def test_vlan_sync_requires_auth(client) -> None:
    assert (await client.post("/api/v1/vlans/sync")).status_code == 401


async def test_vlan_sync_not_configured_returns_400(client, admin_headers) -> None:
    # Hermetic env disables NetBox, so get_inventory_source yields NullSource.
    resp = await client.post("/api/v1/vlans/sync", headers=admin_headers)
    assert resp.status_code == 400


async def test_vlan_sync_creates_then_updates(client, admin_headers) -> None:
    _use_source([_vlan("prod", tag=10), _vlan("dmz", tag=20, description="edge")])
    resp = await client.post("/api/v1/vlans/sync", headers=admin_headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["source"] == "netbox"
    assert body["total"] == 2
    assert body["created"] == 2

    resp = await client.post("/api/v1/vlans/sync", headers=admin_headers)
    body = resp.json()
    assert body["created"] == 0
    assert body["updated"] == 2

    listed = (await client.get("/api/v1/vlans", headers=admin_headers)).json()
    assert {"prod", "dmz"} <= {v["name"] for v in listed}


async def test_vlan_sync_skip_mode(client, admin_headers) -> None:
    _use_source([_vlan("prod", tag=10)])
    await client.post("/api/v1/vlans/sync", headers=admin_headers)
    _use_source([_vlan("prod", tag=99)])
    resp = await client.post("/api/v1/vlans/sync?on_conflict=skip", headers=admin_headers)
    body = resp.json()
    assert body["skipped"] == 1
    assert body["updated"] == 0


async def test_vlan_sync_out_of_range_tag_counted(client, admin_headers) -> None:
    _use_source([_vlan("bad", tag=9999), _vlan("good", tag=30)])
    resp = await client.post("/api/v1/vlans/sync", headers=admin_headers)
    body = resp.json()
    assert body["created"] == 1
    assert body["errors"] == 1
    assert "out-of-range" in body["errors_detail"][0]


async def test_vlan_sync_source_failure_returns_502(client, admin_headers) -> None:
    from portwiz_api.core.inventory_source import get_inventory_source
    from portwiz_api.main import app

    class Boom:
        name = "netbox"

        async def fetch_vlans(self):
            raise RuntimeError("connection refused")

        async def verify(self):
            return False, "x"

    app.dependency_overrides[get_inventory_source] = lambda: Boom()
    resp = await client.post("/api/v1/vlans/sync", headers=admin_headers)
    assert resp.status_code == 502


async def test_vlan_sync_is_audited(client, admin_headers) -> None:
    _use_source([_vlan("prod", tag=10)])
    await client.post("/api/v1/vlans/sync", headers=admin_headers)
    audit = (await client.get("/api/v1/audit", headers=admin_headers)).json()
    assert any(e["action"] == "vlan.synced" for e in audit["events"])
