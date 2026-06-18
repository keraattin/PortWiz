"""The assistant chat turn: ground a model on the current state, let it answer
questions, and let it *propose* (never execute) one catalog action.

The model is asked to reply as JSON ``{"reply": str, "action": {...}|null}``.
Parsing is lenient so a weaker local model that wraps the JSON in prose still
works; if no valid JSON is found we fall back to treating the whole response as
the reply with no action. Any proposed action is validated and built against the
catalog, scoped to the caller's role, before it is returned.
"""

from __future__ import annotations

import json
import re
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from .ai import AIProvider, _clean
from .assistant_actions import (
    CATALOG_BY_NAME,
    ActionError,
    actions_for_role,
    build_snapshot,
)

_MAX_MESSAGES = 20
_MAX_MESSAGE_CHARS = 2000

CHAT_SYSTEM_BASE = (
    "You are PortWiz's in-app assistant. PortWiz monitors open network ports and "
    "services for compliance-driven change detection. Help the user understand the "
    "deployment and, when they ask you to do something, propose exactly one action "
    "for them to confirm. You never perform actions yourself; the user confirms and "
    "the app executes them.\n\n"
    "Always respond with a single JSON object and nothing else:\n"
    '{"reply": "<a short message to the user>", "action": <an action object or null>}\n'
    'An action object is {"name": "<action name>", "args": { ... }}. Propose an '
    "action only when the user clearly asks to create or run something and you have "
    "the required arguments; otherwise set action to null and just answer. Never "
    "invent ids; refer to VLANs, profiles, owners by their name/email. If a needed "
    "argument is missing, ask for it in reply and set action to null."
)


def _catalog_text(role: str) -> str:
    specs = actions_for_role(role)
    if not specs:
        return "(none available for your role; you can only answer questions)"
    return "\n".join(f"- {s.name}: {s.description} Params: {s.params}" for s in specs)


def build_chat_system(role: str, snapshot: str) -> str:
    return (
        f"{CHAT_SYSTEM_BASE}\n\n"
        f"Actions you may propose (only these):\n{_catalog_text(role)}\n\n"
        f"Current PortWiz state:\n{snapshot}"
    )


def format_messages(messages: list[dict[str, str]]) -> str:
    """Flatten the conversation into a single prompt (system is passed
    separately). Each message is cleaned and length-capped."""
    lines: list[str] = []
    for msg in messages[-_MAX_MESSAGES:]:
        role = "User" if msg.get("role") != "assistant" else "Assistant"
        content = _clean(msg.get("content", ""), _MAX_MESSAGE_CHARS)
        if content:
            lines.append(f"{role}: {content}")
    lines.append("Assistant:")
    return "\n".join(lines)


_JSON_RE = re.compile(r"\{.*\}", re.S)


def parse_reply(text: str) -> tuple[str, dict[str, Any] | None]:
    """Extract ``(reply, action)`` from the model output. Tolerant of code
    fences and surrounding prose; falls back to (text, None) on any failure."""
    text = (text or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*", "", text).strip().strip("`").strip()
    match = _JSON_RE.search(text)
    if not match:
        return text, None
    try:
        obj = json.loads(match.group(0))
    except json.JSONDecodeError:
        return text, None
    if not isinstance(obj, dict):
        return text, None
    reply = obj.get("reply")
    action = obj.get("action")
    return (
        reply if isinstance(reply, str) else "",
        action if isinstance(action, dict) else None,
    )


async def run_chat(
    session: AsyncSession,
    provider: AIProvider,
    role: str,
    messages: list[dict[str, str]],
) -> tuple[str, dict[str, Any] | None]:
    """Run one assistant turn. Returns ``(reply, proposed_action | None)`` where a
    proposed action is ``{"name", "summary", "request"}`` ready for the UI."""
    snapshot = await build_snapshot(session)
    system = build_chat_system(role, snapshot)
    raw = await provider.complete(system, format_messages(messages))
    reply, action_obj = parse_reply(raw)

    if not action_obj:
        return reply, None

    name = action_obj.get("name")
    args = action_obj.get("args")
    if not isinstance(args, dict):
        args = {}
    spec = CATALOG_BY_NAME.get(name) if isinstance(name, str) else None
    if spec is None or role not in spec.roles:
        # The model named an action that does not exist or is not allowed for
        # this role; drop it silently and keep the reply.
        return reply, None
    try:
        summary, request = await spec.build(session, args)
    except ActionError as exc:
        suffix = f" ({exc})"
        return (reply + suffix if reply else str(exc)), None
    return reply, {"name": name, "summary": summary, "request": request}
