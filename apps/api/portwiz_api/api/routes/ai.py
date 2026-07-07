"""AI endpoints: fingerprint enrichment and a minimal assistant.

Available to any authenticated user. The provider is selected by configuration
(local Ollama by default, Claude when an API key is set, otherwise a no-op).
Provider/network failures surface as 502 rather than a 500 so the UI can tell
the difference between "AI is unavailable" and a real bug.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.ai import AIProvider, ask_assistant, enrich_fingerprint, get_ai_provider
from ...core.assistant import run_chat
from ...core.db import get_session
from ...core.ratelimit import SlidingWindowLimiter
from ...models.user import User
from ...schemas.ai import (
    AssistantRequest,
    AssistantResponse,
    ChatRequest,
    ChatResponse,
    FingerprintRequest,
    FingerprintResponse,
    ProposedAction,
)
from ..deps import get_current_user

logger = logging.getLogger("portwiz.ai")

router = APIRouter(prefix="/ai", tags=["ai"])

_UNAVAILABLE = HTTPException(status.HTTP_502_BAD_GATEWAY, "AI provider unavailable")

# Cap AI calls per user to bound cost and load (an LLM call is far more expensive
# than an ordinary request, and a paid provider makes this a direct cost vector).
_ai_limiter = SlidingWindowLimiter(max_attempts=30, window_seconds=60)


def ai_rate_limited(current_user: User = Depends(get_current_user)) -> User:
    if not _ai_limiter.check(str(current_user.id)):
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "Too many AI requests. Please slow down.",
        )
    return current_user


@router.post("/fingerprint", response_model=FingerprintResponse)
async def fingerprint(
    payload: FingerprintRequest,
    _: User = Depends(ai_rate_limited),
    provider: AIProvider = Depends(get_ai_provider),
) -> FingerprintResponse:
    try:
        summary = await enrich_fingerprint(
            provider,
            payload.banner,
            payload.port,
            payload.protocol,
            payload.service_hint,
        )
    except Exception as exc:  # external call boundary: never leak a 500
        logger.warning("AI fingerprint failed (%s): %s", provider.name, exc)
        raise _UNAVAILABLE from exc
    return FingerprintResponse(provider=provider.name, summary=summary)


@router.post("/assistant", response_model=AssistantResponse)
async def assistant(
    payload: AssistantRequest,
    _: User = Depends(ai_rate_limited),
    provider: AIProvider = Depends(get_ai_provider),
) -> AssistantResponse:
    try:
        answer = await ask_assistant(provider, payload.question)
    except Exception as exc:  # external call boundary: never leak a 500
        logger.warning("AI assistant failed (%s): %s", provider.name, exc)
        raise _UNAVAILABLE from exc
    return AssistantResponse(provider=provider.name, answer=answer)


@router.post("/chat", response_model=ChatResponse)
async def chat(
    payload: ChatRequest,
    current_user: User = Depends(ai_rate_limited),
    provider: AIProvider = Depends(get_ai_provider),
    session: AsyncSession = Depends(get_session),
) -> ChatResponse:
    """Agentic assistant: answers questions from a live state snapshot and may
    *propose* one role-allowed action for the user to confirm. The action is
    built server-side; nothing is executed here."""
    messages = [{"role": m.role, "content": m.content} for m in payload.messages]
    role = getattr(current_user.role, "value", current_user.role)
    try:
        reply, action = await run_chat(session, provider, role, messages)
    except Exception as exc:  # external call boundary: never leak a 500
        logger.warning("AI chat failed (%s): %s", provider.name, exc)
        raise _UNAVAILABLE from exc
    return ChatResponse(
        provider=provider.name,
        reply=reply,
        action=ProposedAction(**action) if action else None,
    )
