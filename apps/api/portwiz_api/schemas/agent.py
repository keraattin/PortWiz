"""Schemas for scan agents."""

from __future__ import annotations

import datetime as dt
import uuid

from pydantic import BaseModel, ConfigDict, Field


class AgentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    segment: str | None = Field(default=None, max_length=64)


class AgentUpdate(BaseModel):
    segment: str | None = Field(default=None, max_length=64)
    enabled: bool | None = None


class AgentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    segment: str | None
    enabled: bool
    last_seen_at: dt.datetime | None
    token_rotated_at: dt.datetime | None
    created_at: dt.datetime


class AgentCreated(BaseModel):
    """Returned once at enrollment; carries the plaintext token."""

    id: uuid.UUID
    name: str
    segment: str | None
    token: str
    created_at: dt.datetime


class AgentTokenRotated(BaseModel):
    """Returned once after a rotation; carries the new plaintext token."""

    id: uuid.UUID
    name: str
    token: str
    token_rotated_at: dt.datetime
