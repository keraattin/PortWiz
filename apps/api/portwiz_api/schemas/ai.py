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
