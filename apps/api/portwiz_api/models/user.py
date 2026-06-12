"""User and role models."""

from __future__ import annotations

import datetime as dt
import enum
import uuid

from sqlalchemy import Column, DateTime, String
from sqlmodel import Field, SQLModel


class UserRole(str, enum.Enum):
    """Coarse RBAC roles for the MVP.

    admin    - full control, user management, configuration.
    operator - create/run scans, manage assets, work tasks.
    auditor  - read-only access to results, audit log, and evidence.
    """

    admin = "admin"
    operator = "operator"
    auditor = "auditor"


def _utcnow() -> dt.datetime:
    return dt.datetime.now(tz=dt.timezone.utc)


class User(SQLModel, table=True):
    __tablename__ = "users"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    email: str = Field(
        sa_column=Column(String(320), unique=True, index=True, nullable=False)
    )
    hashed_password: str
    full_name: str | None = None
    role: UserRole = Field(
        default=UserRole.operator,
        sa_column=Column(String(32), nullable=False, server_default=UserRole.operator.value),
    )
    is_active: bool = Field(default=True, nullable=False)
    created_at: dt.datetime = Field(
        default_factory=_utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
