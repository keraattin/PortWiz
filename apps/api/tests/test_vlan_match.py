"""Asset-to-VLAN auto-matching: helper, create-time match, and backfill endpoint."""

from __future__ import annotations


async def test_match_ip_prefers_most_specific(db) -> None:
    from portwiz_api.core.inventory_match import load_vlan_ranges, match_ip
    from portwiz_api.models.asset import IPRange, VLAN

    async with db() as session:
        broad = VLAN(name="broad")
        specific = VLAN(name="specific")
        session.add(broad)
        session.add(specific)
        await session.flush()
        broad_id, specific_id = broad.id, specific.id
        session.add(IPRange(cidr="10.0.0.0/8", vlan_id=broad_id))
        session.add(IPRange(cidr="10.1.2.0/24", vlan_id=specific_id))
        await session.commit()
        ranges = await load_vlan_ranges(session)

    assert match_ip(ranges, "10.1.2.5") == specific_id  # longest prefix wins
    assert match_ip(ranges, "10.9.9.9") == broad_id  # only the /8 contains it
    assert match_ip(ranges, "192.168.1.1") is None  # no range
    assert match_ip(ranges, "not-an-ip") is None  # invalid


async def test_create_asset_auto_matches_vlan(client, admin_headers) -> None:
    v = await client.post("/api/v1/vlans", json={"name": "corp"}, headers=admin_headers)
    vid = v.json()["id"]
    await client.post(
        "/api/v1/ip-ranges",
        json={"cidr": "172.16.0.0/16", "vlan_id": vid},
        headers=admin_headers,
    )

    # No vlan_id given: the asset is placed in the VLAN whose range contains it.
    a = await client.post(
        "/api/v1/assets", json={"ip": "172.16.5.9"}, headers=admin_headers
    )
    assert a.status_code == 201, a.text
    assert a.json()["vlan_id"] == vid

    # An IP outside every range stays unmatched.
    b = await client.post(
        "/api/v1/assets", json={"ip": "8.8.8.8"}, headers=admin_headers
    )
    assert b.json()["vlan_id"] is None


async def test_create_asset_keeps_explicit_vlan(client, admin_headers) -> None:
    # An explicit vlan_id is respected even if the IP is not in that VLAN's range.
    v = await client.post("/api/v1/vlans", json={"name": "manual"}, headers=admin_headers)
    vid = v.json()["id"]
    a = await client.post(
        "/api/v1/assets",
        json={"ip": "203.0.113.7", "vlan_id": vid},
        headers=admin_headers,
    )
    assert a.status_code == 201, a.text
    assert a.json()["vlan_id"] == vid


async def test_match_vlans_backfill(client, admin_headers, db) -> None:
    from sqlalchemy import select

    from portwiz_api.models.asset import Asset, Criticality

    v = await client.post("/api/v1/vlans", json={"name": "seg"}, headers=admin_headers)
    vid = v.json()["id"]
    await client.post(
        "/api/v1/ip-ranges",
        json={"cidr": "10.5.0.0/16", "vlan_id": vid},
        headers=admin_headers,
    )
    # Two vlan-less assets: one inside the range, one outside.
    async with db() as session:
        session.add(Asset(ip="10.5.9.9", vlan_id=None, criticality=Criticality.low))
        session.add(Asset(ip="8.8.8.8", vlan_id=None, criticality=Criticality.low))
        await session.commit()

    resp = await client.post("/api/v1/assets/match-vlans", headers=admin_headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["checked"] == 2
    assert body["matched"] == 1

    async with db() as session:
        matched = (
            await session.execute(select(Asset).where(Asset.ip == "10.5.9.9"))
        ).scalars().first()
        unmatched = (
            await session.execute(select(Asset).where(Asset.ip == "8.8.8.8"))
        ).scalars().first()
    assert str(matched.vlan_id) == vid
    assert unmatched.vlan_id is None
