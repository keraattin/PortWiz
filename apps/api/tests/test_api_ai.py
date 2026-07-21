"""API integration tests for the AI chat endpoint.

A fake provider is injected via FastAPI dependency override, so these run with
no Ollama instance and no Claude API key. Rate limiters and dependency overrides
are reset between tests by conftest. The reply-parsing and proposed-action logic
is covered in test_assistant.py; here we exercise the endpoint's cross-cutting
behaviour (auth, validation, rate limiting, provider-failure handling).
"""

from __future__ import annotations


class FakeProvider:
    name = "fake"

    async def complete(self, system: str, user: str) -> str:
        return "Port 22 is SSH."  # plain prose is used verbatim as the reply


def _use_fake_provider() -> None:
    from portwiz_api.core.ai import get_ai_provider
    from portwiz_api.main import app

    app.dependency_overrides[get_ai_provider] = lambda: FakeProvider()


def _chat(text: str = "hello") -> dict:
    return {"messages": [{"role": "user", "content": text}]}


async def test_chat_requires_auth(client) -> None:
    resp = await client.post("/api/v1/ai/chat", json=_chat())
    assert resp.status_code == 401


async def test_chat_returns_reply(client, admin_headers) -> None:
    _use_fake_provider()
    resp = await client.post(
        "/api/v1/ai/chat", json=_chat("what is port 22?"), headers=admin_headers
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["provider"] == "fake"
    assert body["reply"]  # a non-empty reply was produced


async def test_chat_rejects_empty_messages(client, admin_headers) -> None:
    resp = await client.post(
        "/api/v1/ai/chat", json={"messages": []}, headers=admin_headers
    )
    assert resp.status_code == 422


async def test_ai_chat_is_rate_limited(client, admin_headers) -> None:
    _use_fake_provider()
    # 30 calls/min per user are allowed; the 31st is throttled.
    statuses = [
        (await client.post("/api/v1/ai/chat", json=_chat(), headers=admin_headers)).status_code
        for _ in range(31)
    ]
    assert statuses[:30] == [200] * 30
    assert statuses[30] == 429


async def test_chat_provider_failure_returns_502(client, admin_headers) -> None:
    from portwiz_api.core.ai import get_ai_provider
    from portwiz_api.main import app

    class Boom:
        name = "boom"

        async def complete(self, system: str, user: str) -> str:
            raise RuntimeError("provider down")

    app.dependency_overrides[get_ai_provider] = lambda: Boom()
    resp = await client.post("/api/v1/ai/chat", json=_chat(), headers=admin_headers)
    assert resp.status_code == 502
