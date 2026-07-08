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
import logging
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


logger = logging.getLogger("portwiz.assistant")

_JSON_RE = re.compile(r"\{.*\}", re.S)
# Shown when the model produced something that was meant to be structured but
# couldn't be parsed, so we never dump a raw/half-formed JSON blob at the user.
_FALLBACK_REPLY = "Sorry, I couldn't process that. Could you rephrase your request?"
# Shown when the model proposed a valid action but gave no accompanying prose.
_ACTION_REPLY = "I've prepared an action for you. Review and confirm below."


def _extract_json(text: str) -> dict[str, Any] | None:
    """Best-effort extraction of the model's ``{...}`` object, tolerating trailing
    prose and a truncated tail (a weak model that drops the final braces)."""
    # First the greedy match (handles trailing prose after a complete object).
    match = _JSON_RE.search(text)
    if match:
        try:
            obj = json.loads(match.group(0))
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            pass
    # Truncation repair: from the first "{", append up to a few closing braces.
    start = text.find("{")
    if start != -1:
        blob = text[start:]
        for extra in range(1, 4):
            try:
                obj = json.loads(blob + ("}" * extra))
                if isinstance(obj, dict):
                    return obj
            except json.JSONDecodeError:
                continue
    return None


def parse_reply(text: str) -> tuple[str, dict[str, Any] | None]:
    """Extract ``(reply, action)`` from the model output. Tolerant of code fences,
    surrounding prose and a truncated JSON tail. If the model clearly attempted
    structured output but it can't be parsed, return a friendly fallback rather
    than leaking a raw/half-formed JSON blob to the user; plain-prose replies
    (no JSON at all) pass through unchanged."""
    text = (text or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*", "", text).strip().strip("`").strip()
    obj = _extract_json(text)
    if obj is None:
        # No JSON at all -> the model just answered in prose. A "{" that failed to
        # parse means malformed structured output -> don't surface the raw blob.
        if "{" in text:
            logger.warning("assistant: unparseable model output: %r", text[:300])
            return "", None
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
    logger.debug("assistant raw completion: %r", raw[:1000])
    reply, action_obj = parse_reply(raw)

    if not action_obj:
        # Empty reply with no action means we couldn't make sense of the output
        # (e.g. a weak model returned malformed JSON): return a clear fallback
        # instead of a blank message.
        return (reply or _FALLBACK_REPLY), None

    name = action_obj.get("name")
    args = action_obj.get("args")
    if not isinstance(args, dict):
        args = {}
    spec = CATALOG_BY_NAME.get(name) if isinstance(name, str) else None
    if spec is None or role not in spec.roles:
        # The model named an action that does not exist or is not allowed for
        # this role; drop it and keep the reply (or a fallback if it was blank).
        logger.info("assistant: dropped unknown/denied action %r for role %s", name, role)
        return (reply or _FALLBACK_REPLY), None
    try:
        summary, request = await spec.build(session, args)
    except ActionError as exc:
        suffix = f" ({exc})"
        return (reply + suffix if reply else str(exc)), None
    # Always give the user some prose alongside the confirm button, even if the
    # model returned only the action.
    return (reply or _ACTION_REPLY), {"name": name, "summary": summary, "request": request}
