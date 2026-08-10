"""Free-form tags on assets and VLANs: normalization, persistence, update, clear."""

from __future__ import annotations


async def test_asset_tags_normalized_and_persisted(client, admin_headers) -> None:
    # Trim, drop empties, and de-duplicate case-insensitively (first casing wins).
    resp = await client.post(
        "/api/v1/assets",
        json={"ip": "10.1.1.1", "tags": [" web ", "web", "DB", ""]},
        headers=admin_headers,
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["tags"] == ["web", "DB"]
    aid = resp.json()["id"]

    # Update replaces the tag set.
    upd = await client.patch(
        f"/api/v1/assets/{aid}", json={"tags": ["prod", "prod"]}, headers=admin_headers
    )
    assert upd.status_code == 200, upd.text
    assert upd.json()["tags"] == ["prod"]

    # An empty list clears the tags; a get reflects it.
    cleared = await client.patch(
        f"/api/v1/assets/{aid}", json={"tags": []}, headers=admin_headers
    )
    assert cleared.json()["tags"] == []
    got = await client.get(f"/api/v1/assets/{aid}", headers=admin_headers)
    assert got.json()["tags"] == []


async def test_vlan_tags_persisted(client, admin_headers) -> None:
    resp = await client.post(
        "/api/v1/vlans",
        json={"name": "tagged", "tags": ["core", "core", "edge"]},
        headers=admin_headers,
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["tags"] == ["core", "edge"]

    listed = await client.get("/api/v1/vlans", headers=admin_headers)
    tagged = next(v for v in listed.json() if v["name"] == "tagged")
    assert tagged["tags"] == ["core", "edge"]
