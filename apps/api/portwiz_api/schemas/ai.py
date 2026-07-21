"""Schemas for the AI layer."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: str = Field(max_length=16)  # "user" | "assistant"
    content: str = Field(max_length=4000)


class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(min_length=1, max_length=20)


class ActionRequest(BaseModel):
    """The exact REST call the frontend should make to execute the action.
    Built server-side from the catalog, so the path can never be model-chosen."""

    method: str
    path: str
    body: dict | None = None


class ProposedAction(BaseModel):
    name: str
    summary: dict
    request: ActionRequest


class ChatResponse(BaseModel):
    provider: str
    reply: str
    action: ProposedAction | None = None
