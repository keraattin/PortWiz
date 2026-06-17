"""Runtime-editable application settings.

Each row overrides one environment-default configuration value, so operators can
configure integrations from the UI without a redeploy. Effective config is the
environment value overlaid with these overrides. Secret values are stored here
and never returned to clients.
"""

from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import Column, DateTime, String
from sqlmodel import Field, SQLModel


def _utcnow() -> dt.datetime:
    return dt.datetime.now(tz=dt.timezone.utc)


class AppSetting(SQLModel, table=True):
    __tablename__ = "app_settings"

    key: str = Field(sa_column=Column(String(64), primary_key=True))
    value: str | None = Field(default=None, sa_column=Column(String(2048)))
    updated_at: dt.datetime = Field(
        default_factory=_utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_by: uuid.UUID | None = Field(default=None, foreign_key="users.id")
