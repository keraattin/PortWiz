"""API integration tests for the AI endpoints.

A fake provider is injected via FastAPI dependency override, so these run with
no Ollama instance and no Claude API key.
"""

from __future__ import annotations


class FakeProvider:
    name = "fake"

    async def complete(self, system: str, user: str) -> str:
        return "Service: ssh\nVersion: OpenSSH 9.6\nSummary: secure shell"


def _use_fake_provider() -> FakeProvider:
    from portwiz_api.core.ai import get_ai_provider
    from portwiz_api.main import app

    fake = FakeProvider()
    app.dependency_overrides[get_ai_provider] = lambda: fake
    return fake


async def test_fingerprint_requires_auth(client) -> None:
    resp = await client.post("/api/v1/ai/fingerprint", json={"banner": "x"})
    assert resp.status_code == 401


async def test_fingerprint_returns_summary(client, admin_headers) -> None:
    _use_fake_provider()
    resp = await client.post(
        "/api/v1/ai/fingerprint",
        json={"banner": "SSH-2.0-OpenSSH_9.6", "port": 22, "protocol": "tcp"},
        headers=admin_headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["provider"] == "fake"
    assert "ssh" in body["summary"].lower()


async def test_fingerprint_rejects_empty_banner(client, admin_headers) -> None:
    resp = await client.post(
        "/api/v1/ai/fingerprint", json={"banner": ""}, headers=admin_headers
    )
    assert resp.status_code == 422


async def test_assistant_returns_answer(client, admin_headers) -> None:
    _use_fake_provider()
    resp = await client.post(
        "/api/v1/ai/assistant",
        json={"question": "What is port 22?"},
        headers=admin_headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["provider"] == "fake"


async def test_ai_endpoints_are_rate_limited(client, admin_headers) -> None:
    _use_fake_provider()
    body = {"banner": "SSH-2.0-OpenSSH_9.6", "port": 22, "protocol": "tcp"}
    # 30 calls/min per user are allowed; the 31st is throttled.
    statuses = [
        (await client.post("/api/v1/ai/fingerprint", json=body, headers=admin_headers)).status_code
        for _ in range(31)
    ]
    assert statuses[:30] == [200] * 30
    assert statuses[30] == 429


async def test_provider_failure_returns_502(client, admin_headers) -> None:
    from portwiz_api.core.ai import get_ai_provider
    from portwiz_api.main import app

    class Boom:
        name = "boom"

        async def complete(self, system: str, user: str) -> str:
            raise RuntimeError("provider down")

    app.dependency_overrides[get_ai_provider] = lambda: Boom()
    resp = await client.post(
        "/api/v1/ai/assistant", json={"question": "hi"}, headers=admin_headers
    )
    assert resp.status_code == 502
