"""API tests for the offline CVE feed import endpoint (admin-only)."""

from __future__ import annotations

import json

_FEED = json.dumps(
    {
        "vulnerabilities": [
            {
                "cve": {
                    "id": "CVE-2022-9999",
                    "descriptions": [{"lang": "en", "value": "nginx buffer overflow."}],
                    "metrics": {"cvssMetricV31": [{"cvssData": {"baseScore": 8.1}}]},
                    "configurations": [
                        {"nodes": [{"cpeMatch": [{"criteria": "cpe:2.3:a:nginx:nginx:1.20.0:*"}]}]}
                    ],
                }
            }
        ]
    }
).encode()


async def test_import_feed(client, admin_headers) -> None:
    resp = await client.post(
        "/api/v1/cve/import",
        headers=admin_headers,
        files={"file": ("feed.json", _FEED, "application/json")},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total"] == 1
    assert body["imported"] == 1
    assert body["loaded"] >= 1


async def test_import_requires_admin(client, admin_headers) -> None:
    await client.post(
        "/api/v1/users",
        json={"email": "op-cve@test.local", "password": "Secret123!", "role": "operator"},
        headers=admin_headers,
    )
    login = await client.post(
        "/api/v1/auth/login", data={"username": "op-cve@test.local", "password": "Secret123!"}
    )
    hdr = {"Authorization": f"Bearer {login.json()['access_token']}"}
    resp = await client.post(
        "/api/v1/cve/import", headers=hdr, files={"file": ("f.json", _FEED, "application/json")}
    )
    assert resp.status_code == 403


async def test_import_rejects_bad_file(client, admin_headers) -> None:
    resp = await client.post(
        "/api/v1/cve/import",
        headers=admin_headers,
        files={"file": ("f.json", b"not json", "application/json")},
    )
    assert resp.status_code == 400
