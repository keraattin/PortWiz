"""Schemas for tasks."""

from __future__ import annotations

import datetime as dt
import uuid

from pydantic import BaseModel, ConfigDict, Field

from ..models.task import TaskStatus


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    assignee_id: uuid.UUID | None = None
    change_event_id: uuid.UUID | None = None


class TaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    status: TaskStatus | None = None
    assignee_id: uuid.UUID | None = None


class TaskRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    description: str | None
    status: TaskStatus
    change_event_id: uuid.UUID | None
    assignee_id: uuid.UUID | None
    created_by: uuid.UUID | None
    jira_key: str | None
    created_at: dt.datetime
    updated_at: dt.datetime
