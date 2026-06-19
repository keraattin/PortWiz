"""Tests for DB-backed settings overrides and the config endpoints."""

from __future__ import annotations


async def test_effective_settings_applies_overrides(db) -> None:
    from portwiz_api.core.app_settings import effective_settings, set_overrides

    async with db() as session:
        await set_overrides(
            session,
            {"smtp_host": "mail.example.com", "smtp_port": 2525, "notifications_enabled": True},
            actor_id=None,
            actor_email="tester",
        )
    async with db() as session:
        s = await effective_settings(session)
        assert s.smtp_host == "mail.example.com"
        assert s.smtp_port == 2525  # cast back to int
        assert s.notifications_enabled is True  # cast back to bool


async def test_blank_secret_is_not_cleared(db) -> None:
    from portwiz_api.core.app_settings import effective_settings, set_overrides

    async with db() as session:
        await set_overrides(
            session, {"anthropic_api_key": "sk-real"}, actor_id=None, actor_email="t"
        )
    async with db() as session:
        await set_overrides(
            session, {"anthropic_api_key": ""}, actor_id=None, actor_email="t"
        )
    async with db() as session:
        s = await effective_settings(session)
        assert s.anthropic_api_key == "sk-real"


async def test_admin_can_read_config(client, admin_headers) -> None:
    resp = await client.get("/api/v1/settings/config", headers=admin_headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    # Default (no overrides) reflects the hermetic env.
    assert body["ai_provider"] == "ollama"
    assert body["anthropic_api_key_set"] is False


async def test_update_config_applies_and_masks_secrets(client, admin_headers) -> None:
    resp = await client.patch(
        "/api/v1/settings/config",
        json={
            "ai_provider": "claude",
            "anthropic_api_key": "sk-secret-value",
            "anthropic_model": "claude-opus-4-8",
        },
        headers=admin_headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["ai_provider"] == "claude"
    assert body["anthropic_model"] == "claude-opus-4-8"
    assert body["anthropic_api_key_set"] is True
    assert "anthropic_api_key" not in body  # secret never serialized
    assert "sk-secret-value" not in resp.text

    # The status endpoint now reflects the override.
    status = (await client.get("/api/v1/settings", headers=admin_headers)).json()
    assert status["ai_provider"] == "claude"
    assert status["ai_configured"] is True

    # The secret never appears in the config view either.
    cfg = await client.get("/api/v1/settings/config", headers=admin_headers)
    assert "sk-secret-value" not in cfg.text
    assert cfg.json()["anthropic_api_key_set"] is True


async def test_update_config_keeps_existing_secret_on_blank(client, admin_headers) -> None:
    await client.patch(
        "/api/v1/settings/config", json={"jira_api_token": "tok-123"}, headers=admin_headers
    )
    # A later update that omits the token must not clear it.
    await client.patch(
        "/api/v1/settings/config",
        json={"jira_url": "https://acme.atlassian.net", "jira_enabled": True},
        headers=admin_headers,
    )
    cfg = (await client.get("/api/v1/settings/config", headers=admin_headers)).json()
    assert cfg["jira_api_token_set"] is True
    assert cfg["jira_url"] == "https://acme.atlassian.net"
    assert cfg["jira_enabled"] is True


async def test_jira_deepening_fields_round_trip(client, admin_headers) -> None:
    resp = await client.patch(
        "/api/v1/settings/config",
        json={
            "jira_enabled": True,
            "jira_deployment": "server",
            "jira_url": "https://jira.onprem.local",
            "jira_api_token": "pat-token",
            "jira_issue_type": "Incident",
            "jira_default_assignee": "jsmith",
            "jira_labels": "portwiz,security",
        },
        headers=admin_headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["jira_deployment"] == "server"
    assert body["jira_issue_type"] == "Incident"
    assert body["jira_default_assignee"] == "jsmith"
    assert body["jira_labels"] == "portwiz,security"

    # Server/DC needs no email, so the integration counts as configured.
    status = (await client.get("/api/v1/settings", headers=admin_headers)).json()
    assert status["jira_deployment"] == "server"
    assert status["jira_configured"] is True


async def test_jira_cloud_needs_email_to_configure(client, admin_headers) -> None:
    # Cloud without an email is not "configured" even with url + token.
    await client.patch(
        "/api/v1/settings/config",
        json={
            "jira_enabled": True,
            "jira_deployment": "cloud",
            "jira_url": "https://acme.atlassian.net",
            "jira_api_token": "cloud-token",
        },
        headers=admin_headers,
    )
    status = (await client.get("/api/v1/settings", headers=admin_headers)).json()
    assert status["jira_configured"] is False

    await client.patch(
        "/api/v1/settings/config",
        json={"jira_email": "ops@acme.io"},
        headers=admin_headers,
    )
    status = (await client.get("/api/v1/settings", headers=admin_headers)).json()
    assert status["jira_configured"] is True


async def test_compat_secret_masked(client, admin_headers) -> None:
    resp = await client.patch(
        "/api/v1/settings/config",
        json={
            "ai_provider": "openai",
            "compat_api_key": "sk-compat-secret",
            "compat_model": "gpt-4o",
        },
        headers=admin_headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["ai_provider"] == "openai"
    assert body["compat_model"] == "gpt-4o"
    assert body["compat_api_key_set"] is True
    assert "compat_api_key" not in body
    assert "sk-compat-secret" not in resp.text

    # The status endpoint reports the provider as configured (key present).
    status = (await client.get("/api/v1/settings", headers=admin_headers)).json()
    assert status["ai_provider"] == "openai"
    assert status["ai_configured"] is True


async def test_ai_providers_listed(client, admin_headers, db) -> None:
    resp = await client.get("/api/v1/settings/ai-providers", headers=admin_headers)
    assert resp.status_code == 200, resp.text
    ids = {p["id"] for p in resp.json()}
    assert {"ollama", "claude", "openai", "custom"} <= ids

    from portwiz_api.core.security import hash_password
    from portwiz_api.models.user import User, UserRole

    async with db() as session:
        session.add(
            User(
                email="aud-prov@test.local",
                hashed_password=hash_password("Secret123!"),
                full_name="Aud",
                role=UserRole.auditor,
            )
        )
        await session.commit()
    login = await client.post(
        "/api/v1/auth/login",
        data={"username": "aud-prov@test.local", "password": "Secret123!"},
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    assert (await client.get("/api/v1/settings/ai-providers", headers=headers)).status_code == 403


async def test_config_update_requires_admin(client, db) -> None:
    from portwiz_api.core.security import hash_password
    from portwiz_api.models.user import User, UserRole

    async with db() as session:
        session.add(
            User(
                email="op-cfg@test.local",
                hashed_password=hash_password("Secret123!"),
                full_name="Op",
                role=UserRole.operator,
            )
        )
        await session.commit()
    login = await client.post(
        "/api/v1/auth/login", data={"username": "op-cfg@test.local", "password": "Secret123!"}
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    assert (await client.get("/api/v1/settings/config", headers=headers)).status_code == 403
    assert (
        await client.patch("/api/v1/settings/config", json={"smtp_host": "x"}, headers=headers)
    ).status_code == 403
