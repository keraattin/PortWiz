"""Schemas for scan agents."""

from __future__ import annotations

import datetime as dt
import uuid

from pydantic import BaseModel, ConfigDict, Field


class AgentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)


class AgentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    enabled: bool
    last_seen_at: dt.datetime | None
    created_at: dt.datetime


class AgentCreated(BaseModel):
    """Returned once at enrollment; carries the plaintext token."""

    id: uuid.UUID
    name: str
    token: str
    created_at: dt.datetime
