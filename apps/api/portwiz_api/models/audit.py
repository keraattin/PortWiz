"""Immutable, hash-chained audit event model.

See ``portwiz_api.core.audit`` for the append/verify logic.
"""

from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import JSON, Column, DateTime, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel


class AuditEvent(SQLModel, table=True):
    __tablename__ = "audit_events"

    # Monotonic sequence (bigserial). Defines chain order.
    seq: int | None = Field(default=None, primary_key=True)

    actor_id: uuid.UUID | None = Field(default=None, index=True)
    actor_email: str | None = Field(default=None, sa_column=Column(String(320)))
    action: str = Field(sa_column=Column(String(128), nullable=False, index=True))
    target_type: str | None = Field(default=None, sa_column=Column(String(64)))
    target_id: str | None = Field(default=None, sa_column=Column(String(128), index=True))

    # Arbitrary structured detail. JSONB on PostgreSQL, JSON elsewhere (tests).
    payload: dict = Field(
        default_factory=dict,
        sa_column=Column(JSON().with_variant(JSONB(), "postgresql"), nullable=False),
    )

    # Hash chain: hash = sha256(prev_hash || canonical(event fields)).
    prev_hash: str = Field(sa_column=Column(String(64), nullable=False))
    hash: str = Field(sa_column=Column(String(64), nullable=False, index=True))

    created_at: dt.datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )
