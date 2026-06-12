"""Schemas for reading the audit log and its integrity status."""

from __future__ import annotations

import datetime as dt
import uuid

from pydantic import BaseModel, ConfigDict


class AuditEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    seq: int
    actor_id: uuid.UUID | None
    actor_email: str | None
    action: str
    target_type: str | None
    target_id: str | None
    payload: dict
    prev_hash: str
    hash: str
    created_at: dt.datetime


class AuditPage(BaseModel):
    total: int
    events: list[AuditEventRead]


class ChainVerification(BaseModel):
    ok: bool
    broken_seq: int | None
    total: int
