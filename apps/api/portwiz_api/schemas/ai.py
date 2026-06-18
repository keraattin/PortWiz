"""Schemas for the AI layer."""

from __future__ import annotations

from pydantic import BaseModel, Field


class FingerprintRequest(BaseModel):
    banner: str = Field(min_length=1, max_length=8192)
    port: int | None = Field(default=None, ge=0, le=65535)
    protocol: str | None = Field(default=None, max_length=8)
    service_hint: str | None = Field(default=None, max_length=128)


class FingerprintResponse(BaseModel):
    provider: str
    summary: str


class AssistantRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)


class AssistantResponse(BaseModel):
    provider: str
    answer: str


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
