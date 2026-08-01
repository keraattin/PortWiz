"""API tests for external inventory sync (POST /assets/sync).

A fake inventory source is injected via dependency override, so these run with
no NetBox instance.
"""

from __future__ import annotations


class FakeSource:
    name = "netbox"

    def __init__(self, items) -> None:
        self._items = items

    async def fetch_assets(self):
        return self._items

    async def verify(self):
        return True, "ok"


def _use_source(items):
    from portwiz_api.core.inventory_source import get_inventory_source
    from portwiz_api.main import app

    app.dependency_overrides[get_inventory_source] = lambda: FakeSource(items)


def _src(ip, hostname=None, description=None, vlan_name=None):
    from portwiz_api.core.inventory_source import SourceAsset

    return SourceAsset(ip=ip, hostname=hostname, description=description, vlan_name=vlan_name)


async def test_sync_requires_auth(client) -> None:
    assert (await client.post("/api/v1/assets/sync")).status_code == 401


async def test_sync_not_configured_returns_400(client, admin_headers) -> None:
    # Hermetic env disables NetBox, so get_inventory_source yields NullSource.
    resp = await client.post("/api/v1/assets/sync", headers=admin_headers)
    assert resp.status_code == 400


async def test_sync_creates_then_updates(client, admin_headers) -> None:
    _use_source([_src("10.0.0.5", hostname="web01"), _src("10.0.0.6")])
    resp = await client.post("/api/v1/assets/sync", headers=admin_headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["source"] == "netbox"
    assert body["total"] == 2
    assert body["created"] == 2

    resp = await client.post("/api/v1/assets/sync", headers=admin_headers)
    body = resp.json()
    assert body["created"] == 0
    assert body["updated"] == 2

    listed = (await client.get("/api/v1/assets", headers=admin_headers)).json()
    assert {a["ip"] for a in listed} == {"10.0.0.5", "10.0.0.6"}


async def test_sync_skip_mode(client, admin_headers) -> None:
    _use_source([_src("10.0.0.5", hostname="web01")])
    await client.post("/api/v1/assets/sync", headers=admin_headers)
    _use_source([_src("10.0.0.5", hostname="changed")])
    resp = await client.post("/api/v1/assets/sync?on_conflict=skip", headers=admin_headers)
    body = resp.json()
    assert body["skipped"] == 1
    assert body["updated"] == 0


async def test_sync_invalid_ip_is_counted(client, admin_headers) -> None:
    _use_source([_src("not-an-ip"), _src("10.0.0.9")])
    resp = await client.post("/api/v1/assets/sync", headers=admin_headers)
    body = resp.json()
    assert body["created"] == 1
    assert body["errors"] == 1
    assert "Invalid IP" in body["errors_detail"][0]


async def test_sync_resolves_vlan_by_name(client, admin_headers) -> None:
    vlan = (
        await client.post("/api/v1/vlans", json={"name": "prod"}, headers=admin_headers)
    ).json()
    _use_source([_src("10.0.0.10", vlan_name="prod")])
    await client.post("/api/v1/assets/sync", headers=admin_headers)
    asset = (await client.get("/api/v1/assets", headers=admin_headers)).json()[0]
    assert asset["vlan_id"] == vlan["id"]


async def test_sync_source_failure_returns_502(client, admin_headers) -> None:
    from portwiz_api.core.inventory_source import get_inventory_source
    from portwiz_api.main import app

    class Boom:
        name = "netbox"

        async def fetch_assets(self):
            raise RuntimeError("connection refused")

        async def verify(self):
            return False, "x"

    app.dependency_overrides[get_inventory_source] = lambda: Boom()
    resp = await client.post("/api/v1/assets/sync", headers=admin_headers)
    assert resp.status_code == 502


async def test_sync_is_audited(client, admin_headers) -> None:
    _use_source([_src("10.0.0.5")])
    await client.post("/api/v1/assets/sync", headers=admin_headers)
    audit = (await client.get("/api/v1/audit", headers=admin_headers)).json()
    assert any(e["action"] == "asset.synced" for e in audit["events"])


async def test_sync_assets_disabled_returns_400(client, admin_headers) -> None:
    _use_source([_src("10.0.0.5", hostname="web01")])
    await client.patch(
        "/api/v1/settings/config",
        json={"netbox_import_assets": False},
        headers=admin_headers,
    )
    resp = await client.post("/api/v1/assets/sync", headers=admin_headers)
    assert resp.status_code == 400
    assert "disabled" in resp.json()["detail"].lower()


async def test_sync_skips_hostname_when_disabled(client, admin_headers) -> None:
    # A team that owns hostnames locally can pull IPs from NetBox without letting
    # it overwrite their hostnames, while still importing descriptions.
    await client.patch(
        "/api/v1/settings/config",
        json={"netbox_import_hostnames": False},
        headers=admin_headers,
    )
    _use_source([_src("10.0.0.7", hostname="from-netbox", description="owned")])
    resp = await client.post("/api/v1/assets/sync", headers=admin_headers)
    assert resp.status_code == 200, resp.text
    asset = (await client.get("/api/v1/assets", headers=admin_headers)).json()[0]
    assert asset["hostname"] is None
    assert asset["description"] == "owned"


# --- interactive sync (preview + apply) ---


async def test_sync_preview_flags_existing(client, admin_headers) -> None:
    await client.post("/api/v1/assets", json={"ip": "10.0.0.5"}, headers=admin_headers)
    _use_source([_src("10.0.0.5", hostname="web01"), _src("10.0.0.6")])
    resp = await client.get("/api/v1/assets/sync/preview", headers=admin_headers)
    assert resp.status_code == 200, resp.text
    by_ip = {p["ip"]: p for p in resp.json()}
    assert by_ip["10.0.0.5"]["exists"] is True
    assert by_ip["10.0.0.6"]["exists"] is False
    assert by_ip["10.0.0.5"]["hostname"] == "web01"


async def test_sync_preview_not_configured_returns_400(client, admin_headers) -> None:
    # No source override: hermetic env yields a NullSource.
    resp = await client.get("/api/v1/assets/sync/preview", headers=admin_headers)
    assert resp.status_code == 400


async def test_sync_apply_creates_with_attributes(client, admin_headers) -> None:
    resp = await client.post(
        "/api/v1/assets/sync/apply",
        json={
            "items": [
                {"ip": "10.1.0.1", "hostname": "h1", "criticality": "high"},
                {"ip": "10.1.0.2"},
            ]
        },
        headers=admin_headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["created"] == 2
    listed = (await client.get("/api/v1/assets", headers=admin_headers)).json()
    h1 = next(a for a in listed if a["ip"] == "10.1.0.1")
    assert h1["criticality"] == "high" and h1["hostname"] == "h1"


async def test_sync_apply_validates_vlan(client, admin_headers) -> None:
    import uuid

    resp = await client.post(
        "/api/v1/assets/sync/apply",
        json={"items": [{"ip": "10.1.0.3", "vlan_id": str(uuid.uuid4())}]},
        headers=admin_headers,
    )
    assert resp.status_code == 400  # referenced VLAN does not exist


async def test_sync_apply_requires_write(client, admin_headers) -> None:
    await client.post(
        "/api/v1/users",
        json={"email": "sa-aud@test.local", "password": "Secret123!", "role": "auditor"},
        headers=admin_headers,
    )
    login = await client.post(
        "/api/v1/auth/login", data={"username": "sa-aud@test.local", "password": "Secret123!"}
    )
    aud = {"Authorization": f"Bearer {login.json()['access_token']}"}
    resp = await client.post(
        "/api/v1/assets/sync/apply", json={"items": [{"ip": "10.1.0.9"}]}, headers=aud
    )
    assert resp.status_code == 403
