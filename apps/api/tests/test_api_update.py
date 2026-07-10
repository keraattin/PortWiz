"""API tests for the update-check endpoint (admin-only)."""

from __future__ import annotations

import httpx


def _mock_latest(tag: str):
    from portwiz_api.core import update_check

    update_check.reset_cache()

    def handler(req):
        return httpx.Response(200, json={"tag_name": tag, "html_url": "https://gh/rel"})

    return lambda: httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def test_update_status_reports_available(client, admin_headers, monkeypatch) -> None:
    from portwiz_api.core import update_check

    monkeypatch.setattr(update_check, "_client", _mock_latest("v99.0.0"))
    resp = await client.get("/api/v1/update/status", headers=admin_headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["enabled"] is True
    assert body["latest"] == "99.0.0"
    assert body["update_available"] is True  # 99.0.0 > packaged version
    assert body["url"] == "https://gh/rel"


async def test_update_status_requires_admin(client, admin_headers) -> None:
    await client.post(
        "/api/v1/users",
        json={"email": "op-upd@test.local", "password": "Secret123!", "role": "operator"},
        headers=admin_headers,
    )
    login = await client.post(
        "/api/v1/auth/login", data={"username": "op-upd@test.local", "password": "Secret123!"}
    )
    hdr = {"Authorization": f"Bearer {login.json()['access_token']}"}
    assert (await client.get("/api/v1/update/status", headers=hdr)).status_code == 403


async def test_update_check_forces_refresh(client, admin_headers, monkeypatch) -> None:
    from portwiz_api.core import update_check

    monkeypatch.setattr(update_check, "_client", _mock_latest("v99.9.9"))
    resp = await client.post("/api/v1/update/check", headers=admin_headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["latest"] == "99.9.9"


async def _enable_apply(db) -> None:
    """Turn on one-click apply the way a deployment does: the env flag. It is not
    a UI-editable setting, so we set it as an app_settings override directly."""
    from portwiz_api.models.app_setting import AppSetting

    async with db() as session:
        session.add(AppSetting(key="update_apply_enabled", value="true"))
        await session.commit()


async def test_update_apply_disabled_returns_400(client, admin_headers) -> None:
    # Default install has no updater sidecar, so one-click apply is unavailable.
    resp = await client.post("/api/v1/update/apply", headers=admin_headers)
    assert resp.status_code == 400, resp.text


async def test_update_status_reports_apply_available(client, admin_headers, db) -> None:
    from portwiz_api.models.app_setting import AppSetting

    await _enable_apply(db)
    # Disable the GitHub check so status resolves offline and deterministically;
    # apply_available is reported regardless of the check.
    async with db() as session:
        session.add(AppSetting(key="update_check_enabled", value="false"))
        await session.commit()
    resp = await client.get("/api/v1/update/status", headers=admin_headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["enabled"] is False
    assert body["apply_available"] is True


async def test_update_apply_records_request_and_audits(client, admin_headers, db) -> None:
    from sqlalchemy import select

    from portwiz_api.models.app_setting import AppSetting
    from portwiz_api.models.audit import AuditEvent

    await _enable_apply(db)
    resp = await client.post("/api/v1/update/apply", headers=admin_headers)
    assert resp.status_code == 202, resp.text
    assert resp.json()["status"] == "requested"

    async with db() as session:
        flag = await session.get(AppSetting, "update_requested_at")
        assert flag is not None and flag.value  # a timestamp was recorded
        actions = (await session.execute(select(AuditEvent.action))).scalars().all()
        assert "update.requested" in actions


async def test_update_apply_requires_admin(client, admin_headers, db) -> None:
    await _enable_apply(db)
    await client.post(
        "/api/v1/users",
        json={"email": "op-apply@test.local", "password": "Secret123!", "role": "operator"},
        headers=admin_headers,
    )
    login = await client.post(
        "/api/v1/auth/login", data={"username": "op-apply@test.local", "password": "Secret123!"}
    )
    hdr = {"Authorization": f"Bearer {login.json()['access_token']}"}
    assert (await client.post("/api/v1/update/apply", headers=hdr)).status_code == 403
