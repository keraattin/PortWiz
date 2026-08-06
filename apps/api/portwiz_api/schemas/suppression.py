"""Schemas for port false-positive suppressions."""

from __future__ import annotations

import datetime as dt
import uuid

from pydantic import BaseModel, ConfigDict, Field


class SuppressionCreate(BaseModel):
    ip: str = Field(min_length=1, max_length=45)
    port: int = Field(ge=1, le=65535)
    protocol: str = Field(default="tcp", pattern="^(tcp|udp)$")
    reason: str | None = Field(default=None, max_length=256)


class SuppressionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    ip: str
    port: int
    protocol: str
    reason: str | None
    created_by: uuid.UUID | None
    created_at: dt.datetime
