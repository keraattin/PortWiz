"""AI endpoints: fingerprint enrichment and a minimal assistant.

Available to any authenticated user. The provider is selected by configuration
(local Ollama by default, Claude when an API key is set, otherwise a no-op).
Provider/network failures surface as 502 rather than a 500 so the UI can tell
the difference between "AI is unavailable" and a real bug.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status

from ...core.ai import AIProvider, ask_assistant, enrich_fingerprint, get_ai_provider
from ...models.user import User
from ...schemas.ai import (
    AssistantRequest,
    AssistantResponse,
    FingerprintRequest,
    FingerprintResponse,
)
from ..deps import get_current_user

logger = logging.getLogger("portwiz.ai")

router = APIRouter(prefix="/ai", tags=["ai"])

_UNAVAILABLE = HTTPException(status.HTTP_502_BAD_GATEWAY, "AI provider unavailable")


@router.post("/fingerprint", response_model=FingerprintResponse)
async def fingerprint(
    payload: FingerprintRequest,
    _: User = Depends(get_current_user),
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
    _: User = Depends(get_current_user),
    provider: AIProvider = Depends(get_ai_provider),
) -> AssistantResponse:
    try:
        answer = await ask_assistant(provider, payload.question)
    except Exception as exc:  # external call boundary: never leak a 500
        logger.warning("AI assistant failed (%s): %s", provider.name, exc)
        raise _UNAVAILABLE from exc
    return AssistantResponse(provider=provider.name, answer=answer)
