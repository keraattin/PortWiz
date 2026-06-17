"""Schemas for compliance cadence reporting."""

from __future__ import annotations

import datetime as dt
import uuid

from pydantic import BaseModel


class ComplianceStatusItem(BaseModel):
    profile_id: uuid.UUID
    profile_name: str
    framework: str
    cadence_days: int
    last_scan_at: dt.datetime | None
    days_since: int | None
    status: str  # compliant | due_soon | overdue | never
    scan_source: str
    asv_satisfied: bool
