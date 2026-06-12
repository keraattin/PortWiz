"""Schemas for change events."""

from __future__ import annotations

import datetime as dt
import uuid

from pydantic import BaseModel, ConfigDict, Field


class ChangeEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    scan_profile_id: uuid.UUID
    scan_run_id: uuid.UUID | None
    asset_id: uuid.UUID | None
    ip: str
    port: int
    protocol: str
    change_type: str
    before: dict
    after: dict
    severity: str
    status: str
    detected_at: dt.datetime


class ChangeEventUpdate(BaseModel):
    status: str = Field(pattern="^(open|acknowledged|resolved)$")
