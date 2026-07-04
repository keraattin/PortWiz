"""Tests for the agentic assistant: catalog, parsing, and the chat turn.

The assistant proposes actions but never executes them; these tests assert the
role gating, reference resolution, and lenient parsing that make that safe.
"""

from __future__ import annotations


class FakeProvider:
    name = "fake"

    def __init__(self, text: str) -> None:
        self._text = text

    async def complete(self, system: str, user: str) -> str:
        return self._text


def test_actions_for_role() -> None:
    from portwiz_api.core.assistant_actions import actions_for_role

    operator = {a.name for a in actions_for_role("operator")}
    assert "vlan.create" in operator
    assert "scan.run" in operator
    assert "change.acknowledge" in operator
    assert "task.update_status" in operator
    assert "agent.enroll" not in operator  # admin-only

    admin = {a.name for a in actions_for_role("admin")}
    assert "agent.enroll" in admin

    assert actions_for_role("auditor") == []  # read-only role proposes nothing


def test_parse_reply_variants() -> None:
    from portwiz_api.core.assistant import parse_reply

    reply, action = parse_reply('{"reply": "hi", "action": null}')
    assert reply == "hi" and action is None

    reply, action = parse_reply(
        '```json\n{"reply": "x", "action": {"name": "vlan.create", "args": {}}}\n```'
    )
    assert action is not None and action["name"] == "vlan.create"

    # Prose with no JSON falls back to the whole text as the reply.
    reply, action = parse_reply("Port 22 is SSH.")
    assert reply == "Port 22 is SSH." and action is None

    # Truncated JSON tail (weak model dropped the closing braces) is repaired.
    reply, action = parse_reply(
        '{"reply": "Running it.", "action": {"name": "scan.run", "args": {"profile_name": "Weekly"}'
    )
    assert action is not None and action["name"] == "scan.run"

    # Malformed structured output must NOT leak the raw blob to the user.
    reply, action = parse_reply('{"reply": "oops" garbage not json')
    assert reply == "" and action is None


async def test_run_chat_proposes_vlan(db) -> None:
    from portwiz_api.core.assistant import run_chat

    text = (
        '{"reply": "Sure, creating it.", "action": {"name": "vlan.create", '
        '"args": {"name": "DMZ", "vlan_tag": 10}}}'
    )
    msgs = [{"role": "user", "content": "add vlan DMZ"}]
    async with db() as session:
        reply, action = await run_chat(session, FakeProvider(text), "operator", msgs)
    assert "creating" in reply.lower()
    assert action is not None
    assert action["name"] == "vlan.create"
    assert action["request"]["method"] == "POST"
    assert action["request"]["path"] == "/vlans"
    assert action["request"]["body"]["name"] == "DMZ"
    assert action["request"]["body"]["vlan_tag"] == 10
    assert action["summary"]["name"] == "DMZ"


async def test_run_chat_auditor_cannot_act(db) -> None:
    from portwiz_api.core.assistant import run_chat

    text = '{"reply": "ok", "action": {"name": "vlan.create", "args": {"name": "X"}}}'
    msgs = [{"role": "user", "content": "add vlan X"}]
    async with db() as session:
        reply, action = await run_chat(session, FakeProvider(text), "auditor", msgs)
    assert action is None  # write action dropped for a read-only role


async def test_run_chat_query_only(db) -> None:
    from portwiz_api.core.assistant import run_chat

    text = '{"reply": "You currently have 0 assets.", "action": null}'
    msgs = [{"role": "user", "content": "how many assets?"}]
    async with db() as session:
        reply, action = await run_chat(session, FakeProvider(text), "operator", msgs)
    assert action is None and "0 assets" in reply


async def test_run_chat_malformed_output_returns_fallback(db) -> None:
    from portwiz_api.core.assistant import _FALLBACK_REPLY, run_chat

    # A weak model returns unparseable structured output; the user gets a clear
    # fallback, never a blank message or a raw JSON blob.
    text = '{"reply": "half" this is broken not json'
    msgs = [{"role": "user", "content": "create a vlan"}]
    async with db() as session:
        reply, action = await run_chat(session, FakeProvider(text), "operator", msgs)
    assert action is None
    assert reply == _FALLBACK_REPLY


async def test_run_chat_action_without_reply_defaults_to_summary(db) -> None:
    from portwiz_api.core.assistant import run_chat

    # Model proposes a valid action but no prose; the reply falls back to the
    # action summary so the user always sees a description.
    text = '{"reply": "", "action": {"name": "vlan.create", "args": {"name": "NetA", "vlan_tag": 5}}}'
    msgs = [{"role": "user", "content": "add vlan NetA"}]
    async with db() as session:
        reply, action = await run_chat(session, FakeProvider(text), "operator", msgs)
    assert action is not None and action["name"] == "vlan.create"
    assert isinstance(reply, str) and reply.strip()  # never blank


async def test_run_chat_unknown_reference_is_reported(db) -> None:
    from portwiz_api.core.assistant import run_chat

    text = (
        '{"reply": "Adding it.", "action": {"name": "asset.create", '
        '"args": {"ip": "10.0.0.5", "vlan_name": "Ghost"}}}'
    )
    msgs = [{"role": "user", "content": "add asset"}]
    async with db() as session:
        reply, action = await run_chat(session, FakeProvider(text), "operator", msgs)
    assert action is None  # the referenced VLAN does not exist
    assert "not found" in reply.lower()


async def test_run_chat_plain_prose_fallback(db) -> None:
    from portwiz_api.core.assistant import run_chat

    async with db() as session:
        reply, action = await run_chat(
            session,
            FakeProvider("Port 22 is SSH."),
            "operator",
            [{"role": "user", "content": "what is port 22?"}],
        )
    assert action is None and "SSH" in reply


async def test_run_chat_change_acknowledge(db) -> None:
    import uuid

    from portwiz_api.core.assistant import run_chat
    from portwiz_api.models.change import ChangeEvent

    async with db() as session:
        session.add(
            ChangeEvent(
                scan_profile_id=uuid.uuid4(),
                ip="10.0.0.9",
                port=443,
                protocol="tcp",
                change_type="opened",
                severity="high",
            )
        )
        await session.commit()

    text = (
        '{"reply": "Acknowledging.", "action": {"name": "change.acknowledge", '
        '"args": {"ip": "10.0.0.9", "port": 443}}}'
    )
    msgs = [{"role": "user", "content": "ack the change on 10.0.0.9:443"}]
    async with db() as session:
        reply, action = await run_chat(session, FakeProvider(text), "operator", msgs)
    assert action is not None
    assert action["name"] == "change.acknowledge"
    assert action["request"]["method"] == "PATCH"
    assert action["request"]["path"].startswith("/changes/")
    assert action["request"]["body"] == {"status": "acknowledged"}
    assert action["summary"]["target"] == "10.0.0.9:443/tcp"


async def test_run_chat_change_not_found(db) -> None:
    from portwiz_api.core.assistant import run_chat

    text = (
        '{"reply": "OK.", "action": {"name": "change.resolve", '
        '"args": {"ip": "1.2.3.4", "port": 80}}}'
    )
    msgs = [{"role": "user", "content": "resolve change on 1.2.3.4:80"}]
    async with db() as session:
        reply, action = await run_chat(session, FakeProvider(text), "operator", msgs)
    assert action is None
    assert "no change found" in reply.lower()


async def test_run_chat_task_update_status(db) -> None:
    from portwiz_api.core.assistant import run_chat
    from portwiz_api.models.task import Task, TaskStatus

    async with db() as session:
        session.add(Task(title="Review 10.0.0.9:443", status=TaskStatus.open))
        await session.commit()

    text = (
        '{"reply": "Updating.", "action": {"name": "task.update_status", '
        '"args": {"title": "Review 10.0.0.9:443", "status": "done"}}}'
    )
    msgs = [{"role": "user", "content": "mark that task done"}]
    async with db() as session:
        reply, action = await run_chat(session, FakeProvider(text), "operator", msgs)
    assert action is not None
    assert action["name"] == "task.update_status"
    assert action["request"]["path"].startswith("/tasks/")
    assert action["request"]["body"] == {"status": "done"}


async def test_chat_endpoint_proposes_action(client, admin_headers) -> None:
    from portwiz_api.core.ai import get_ai_provider
    from portwiz_api.main import app

    class _Fake:
        name = "fake"

        async def complete(self, system: str, user: str) -> str:
            return (
                '{"reply": "Creating VLAN.", "action": {"name": "vlan.create", '
                '"args": {"name": "Office", "vlan_tag": 20}}}'
            )

    app.dependency_overrides[get_ai_provider] = lambda: _Fake()
    try:
        resp = await client.post(
            "/api/v1/ai/chat",
            json={"messages": [{"role": "user", "content": "add vlan Office"}]},
            headers=admin_headers,
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["reply"] == "Creating VLAN."
        assert body["action"]["name"] == "vlan.create"
        assert body["action"]["request"]["path"] == "/vlans"
        assert body["action"]["request"]["body"]["name"] == "Office"
        assert body["action"]["summary"]["vlan_tag"] == 20
    finally:
        del app.dependency_overrides[get_ai_provider]
