"""API tests for the settings / integration-status surface."""

from __future__ import annotations


async def test_status_requires_auth(client) -> None:
    resp = await client.get("/api/v1/settings")
    assert resp.status_code == 401


async def test_status_exposes_no_secrets(client, admin_headers) -> None:
    resp = await client.get("/api/v1/settings", headers=admin_headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    # Defaults from the hermetic test env.
    assert body["ai_provider"] == "ollama"
    assert body["email_enabled"] is False
    assert body["jira_enabled"] is False
    assert body["jira_configured"] is False
    assert body["netbox_enabled"] is False
    assert body["netbox_configured"] is False
    assert isinstance(body["email_recipients"], list)
    # No secret field should ever be serialized.
    blob = resp.text.lower()
    for secret in ("api_key", "password", "api_token", "secret_key", "token_hash"):
        assert secret not in blob


async def test_test_ai_with_fake_provider(client, admin_headers) -> None:
    from portwiz_api.core.ai import get_ai_provider
    from portwiz_api.main import app

    class FakeProvider:
        name = "fake"

        async def complete(self, system: str, user: str) -> str:
            return "OK"

    app.dependency_overrides[get_ai_provider] = lambda: FakeProvider()
    resp = await client.post("/api/v1/settings/test/ai", headers=admin_headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["ok"] is True
    assert "fake" in body["detail"]


async def test_test_email_disabled_by_default(client, admin_headers) -> None:
    # The hermetic env disables notifications, so get_notifier yields NullNotifier.
    resp = await client.post(
        "/api/v1/settings/test/email", json={"recipient": "x@y.local"}, headers=admin_headers
    )
    assert resp.status_code == 200
    assert resp.json()["ok"] is False


async def test_test_email_with_fake_notifier(client, admin_headers) -> None:
    from portwiz_api.core.notifications import get_notifier
    from portwiz_api.main import app

    sent: list[tuple[str, list[str]]] = []

    class FakeNotifier:
        async def send(self, subject: str, body: str, recipients: list[str]) -> None:
            sent.append((subject, recipients))

    app.dependency_overrides[get_notifier] = lambda: FakeNotifier()
    resp = await client.post(
        "/api/v1/settings/test/email",
        json={"recipient": "ops@test.local"},
        headers=admin_headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["ok"] is True
    assert sent and sent[0][1] == ["ops@test.local"]


async def test_test_jira_uses_tracker_verify(client, admin_headers) -> None:
    from portwiz_api.core.issue_tracker import get_issue_tracker
    from portwiz_api.main import app

    class FakeTracker:
        async def verify(self) -> tuple[bool, str]:
            return True, "Connected to Jira as Tester"

    app.dependency_overrides[get_issue_tracker] = lambda: FakeTracker()
    resp = await client.post("/api/v1/settings/test/jira", headers=admin_headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["ok"] is True
    assert "Tester" in body["detail"]


async def test_jira_discovery_400_when_unconfigured(client, admin_headers) -> None:
    # The hermetic env has no Jira, so get_issue_tracker yields a NullTracker.
    resp = await client.get("/api/v1/settings/jira/projects", headers=admin_headers)
    assert resp.status_code == 400


async def test_jira_discovery_endpoints(client, admin_headers) -> None:
    from portwiz_api.core.issue_tracker import get_issue_tracker
    from portwiz_api.main import app

    class FakeDiscoveryTracker:
        async def list_projects(self) -> list[dict[str, str]]:
            return [{"key": "SEC", "name": "Security"}, {"key": "OPS", "name": "Operations"}]

        async def search_assignable_users(
            self, query: str, project: str | None
        ) -> list[dict[str, str]]:
            assert project == "SEC"
            return [{"id": "acc-1", "label": "Jane (jane@acme.io)"}]

        async def list_issue_types(self) -> list[str]:
            return ["Task", "Bug", "Incident"]

    app.dependency_overrides[get_issue_tracker] = lambda: FakeDiscoveryTracker()

    projects = await client.get("/api/v1/settings/jira/projects", headers=admin_headers)
    assert projects.status_code == 200, projects.text
    assert {p["key"] for p in projects.json()} == {"SEC", "OPS"}

    users = await client.get(
        "/api/v1/settings/jira/users?q=ja&project=SEC", headers=admin_headers
    )
    assert users.status_code == 200, users.text
    assert users.json()[0]["id"] == "acc-1"

    types = await client.get("/api/v1/settings/jira/issue-types", headers=admin_headers)
    assert types.status_code == 200, types.text
    assert types.json() == ["Task", "Bug", "Incident"]


async def test_jira_discovery_admin_only(client, db) -> None:
    from portwiz_api.core.security import hash_password
    from portwiz_api.models.user import User, UserRole

    async with db() as session:
        session.add(
            User(
                email="aud-jira@test.local",
                hashed_password=hash_password("Secret123!"),
                full_name="Aud",
                role=UserRole.auditor,
            )
        )
        await session.commit()
    login = await client.post(
        "/api/v1/auth/login",
        data={"username": "aud-jira@test.local", "password": "Secret123!"},
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    resp = await client.get("/api/v1/settings/jira/projects", headers=headers)
    assert resp.status_code == 403


async def test_test_netbox_uses_source_verify(client, admin_headers) -> None:
    from portwiz_api.core.inventory_source import get_inventory_source
    from portwiz_api.main import app

    class FakeSource:
        name = "netbox"

        async def verify(self) -> tuple[bool, str]:
            return True, "Connected to NetBox 4.1.0"

    app.dependency_overrides[get_inventory_source] = lambda: FakeSource()
    resp = await client.post("/api/v1/settings/test/netbox", headers=admin_headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["ok"] is True
    assert "NetBox" in body["detail"]


async def test_test_actions_are_admin_only(client, db) -> None:
    from portwiz_api.core.security import hash_password
    from portwiz_api.models.user import User, UserRole

    async with db() as session:
        session.add(
            User(
                email="op@test.local",
                hashed_password=hash_password("Secret123!"),
                full_name="Operator",
                role=UserRole.operator,
            )
        )
        await session.commit()
    login = await client.post(
        "/api/v1/auth/login", data={"username": "op@test.local", "password": "Secret123!"}
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    # Operators can read status...
    assert (await client.get("/api/v1/settings", headers=headers)).status_code == 200
    # ...but cannot run test actions.
    assert (await client.post("/api/v1/settings/test/jira", headers=headers)).status_code == 403
