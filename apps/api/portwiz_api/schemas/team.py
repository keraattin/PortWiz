"""Schemas for teams and their membership."""

from __future__ import annotations

import datetime as dt
import uuid

from pydantic import BaseModel, ConfigDict, Field


class TeamCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    description: str | None = None


class TeamUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    description: str | None = None


class TeamRead(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    created_at: dt.datetime
    member_count: int = 0


class TeamMemberRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: uuid.UUID
    email: str
    full_name: str | None = None


class TeamDetail(TeamRead):
    members: list[TeamMemberRead] = []


class TeamMemberAdd(BaseModel):
    user_id: uuid.UUID
