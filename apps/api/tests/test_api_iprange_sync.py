"""API tests for external IP range sync (POST /ip-ranges/sync).

A fake inventory source is injected via dependency override, so these run with
no NetBox instance.
"""

from __future__ import annotations


class FakeSource:
    name = "netbox"

    def __init__(self, items) -> None:
        self._items = items

    async def fetch_ranges(self):
        return self._items

    async def verify(self):
        return True, "ok"


def _use_source(items):
    from portwiz_api.core.inventory_source import get_inventory_source
    from portwiz_api.main import app

    app.dependency_overrides[get_inventory_source] = lambda: FakeSource(items)


def _range(cidr, vlan_name=None, description=None):
    from portwiz_api.core.inventory_source import SourceRange

    return SourceRange(cidr=cidr, vlan_name=vlan_name, description=description)


async def _login(client, email) -> dict[str, str]:
    resp = await client.post(
        "/api/v1/auth/login", data={"username": email, "password": "Secret123!"}
    )
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


async def test_range_sync_requires_auth(client) -> None:
    assert (await client.post("/api/v1/ip-ranges/sync")).status_code == 401


async def test_range_sync_not_configured_returns_400(client, admin_headers) -> None:
    # Hermetic env disables NetBox, so the dependency yields a NullSource.
    resp = await client.post("/api/v1/ip-ranges/sync", headers=admin_headers)
    assert resp.status_code == 400


async def test_range_sync_creates_and_assigns_vlan(client, admin_headers) -> None:
    await client.post("/api/v1/vlans", json={"name": "prod"}, headers=admin_headers)
    _use_source([_range("10.0.0.0/24", vlan_name="prod"), _range("10.0.1.5/24")])
    resp = await client.post("/api/v1/ip-ranges/sync", headers=admin_headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["source"] == "netbox"
    assert body["total"] == 2 and body["created"] == 2

    ranges = (await client.get("/api/v1/ip-ranges", headers=admin_headers)).json()
    cidrs = {r["cidr"] for r in ranges}
    assert "10.0.0.0/24" in cidrs and "10.0.1.0/24" in cidrs  # normalised
    vlans = (await client.get("/api/v1/vlans", headers=admin_headers)).json()
    prod = next(v for v in vlans if v["name"] == "prod")
    prod_range = next(r for r in ranges if r["cidr"] == "10.0.0.0/24")
    assert prod_range["vlan_id"] == prod["id"]

    # Re-syncing updates the existing CIDRs (default on_conflict=update).
    _use_source([_range("10.0.0.0/24", vlan_name="prod")])
    again = await client.post("/api/v1/ip-ranges/sync", headers=admin_headers)
    assert again.json()["updated"] == 1


async def test_range_sync_skip_mode(client, admin_headers) -> None:
    _use_source([_range("10.2.0.0/24")])
    await client.post("/api/v1/ip-ranges/sync", headers=admin_headers)
    _use_source([_range("10.2.0.0/24", description="edge")])
    resp = await client.post(
        "/api/v1/ip-ranges/sync?on_conflict=skip", headers=admin_headers
    )
    assert resp.json()["skipped"] == 1


async def test_range_sync_disabled_returns_400(client, admin_headers) -> None:
    _use_source([_range("10.3.0.0/24")])
    await client.patch(
        "/api/v1/settings/config", json={"netbox_import_vlans": False}, headers=admin_headers
    )
    resp = await client.post("/api/v1/ip-ranges/sync", headers=admin_headers)
    assert resp.status_code == 400


async def test_range_sync_requires_write(client, admin_headers) -> None:
    await client.post(
        "/api/v1/users",
        json={"email": "raud@test.local", "password": "Secret123!", "role": "auditor"},
        headers=admin_headers,
    )
    aud = await _login(client, "raud@test.local")
    assert (await client.post("/api/v1/ip-ranges/sync", headers=aud)).status_code == 403


# --- interactive sync (preview + apply) ---


async def test_range_sync_preview_flags_existing(client, admin_headers) -> None:
    await client.post("/api/v1/ip-ranges", json={"cidr": "10.0.0.0/24"}, headers=admin_headers)
    _use_source([_range("10.0.0.0/24"), _range("10.5.0.0/24")])
    resp = await client.get("/api/v1/ip-ranges/sync/preview", headers=admin_headers)
    assert resp.status_code == 200, resp.text
    by_cidr = {p["cidr"]: p for p in resp.json()}
    assert by_cidr["10.0.0.0/24"]["exists"] is True
    assert by_cidr["10.5.0.0/24"]["exists"] is False


async def test_range_sync_apply_creates_with_vlan(client, admin_headers) -> None:
    vlan = (
        await client.post("/api/v1/vlans", json={"name": "prod"}, headers=admin_headers)
    ).json()
    resp = await client.post(
        "/api/v1/ip-ranges/sync/apply",
        json={"items": [{"cidr": "10.6.0.0/24", "vlan_name": "prod"}, {"cidr": "10.7.0.5/24"}]},
        headers=admin_headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["created"] == 2
    ranges = (await client.get("/api/v1/ip-ranges", headers=admin_headers)).json()
    prod_range = next(r for r in ranges if r["cidr"] == "10.6.0.0/24")
    assert prod_range["vlan_id"] == vlan["id"]
