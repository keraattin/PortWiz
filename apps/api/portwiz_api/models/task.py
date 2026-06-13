"""Task model.

A Task is the unit of follow-up work. One is created automatically whenever a
change is confirmed, and tasks can also be created manually. Jira sync (M5.3)
stores the external key in ``jira_key``.
"""

from __future__ import annotations

import datetime as dt
import enum
import uuid

from sqlalchemy import Column, DateTime, String
from sqlmodel import Field, SQLModel


def _utcnow() -> dt.datetime:
    return dt.datetime.now(tz=dt.timezone.utc)


class TaskStatus(str, enum.Enum):
    open = "open"
    in_progress = "in_progress"
    done = "done"
    cancelled = "cancelled"


class Task(SQLModel, table=True):
    __tablename__ = "tasks"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    title: str = Field(sa_column=Column(String(255), nullable=False))
    description: str | None = None
    status: TaskStatus = Field(
        default=TaskStatus.open,
        sa_column=Column(String(16), nullable=False, server_default=TaskStatus.open.value),
    )
    change_event_id: uuid.UUID | None = Field(
        default=None, foreign_key="change_events.id", index=True
    )
    assignee_id: uuid.UUID | None = Field(default=None, foreign_key="users.id", index=True)
    created_by: uuid.UUID | None = Field(default=None, foreign_key="users.id")
    jira_key: str | None = Field(default=None, sa_column=Column(String(64), index=True))
    created_at: dt.datetime = Field(
        default_factory=_utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_at: dt.datetime = Field(
        default_factory=_utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
