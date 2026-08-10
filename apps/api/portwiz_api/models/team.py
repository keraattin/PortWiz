"""Teams: named groups of users that assets and VLANs can be assigned to.

Membership is a simple user-to-team link. Assignment is an ``owner_team_id`` on
assets and VLANs (alongside the per-user ``owner_id``). No access control is
derived from teams yet; they are ownership/organization only.
"""

from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import Column, DateTime, String, UniqueConstraint
from sqlmodel import Field, SQLModel


def _utcnow() -> dt.datetime:
    return dt.datetime.now(tz=dt.timezone.utc)


class Team(SQLModel, table=True):
    __tablename__ = "teams"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str = Field(
        sa_column=Column(String(128), unique=True, index=True, nullable=False)
    )
    description: str | None = None
    created_at: dt.datetime = Field(
        default_factory=_utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class TeamMember(SQLModel, table=True):
    __tablename__ = "team_members"
    __table_args__ = (
        UniqueConstraint("team_id", "user_id", name="uq_team_member"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    team_id: uuid.UUID = Field(foreign_key="teams.id", nullable=False)
    user_id: uuid.UUID = Field(foreign_key="users.id", nullable=False)
    created_at: dt.datetime = Field(
        default_factory=_utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
