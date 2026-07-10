"""Schemas for compliance cadence reporting."""

from __future__ import annotations

import datetime as dt
import uuid

from pydantic import BaseModel


class FrameworkTemplateRead(BaseModel):
    """A framework's required cadence and a schedule that satisfies it."""

    framework: str
    label: str
    cadence_days: int
    recommended_cron: str
    recommended_label: str
    requires_external_asv: bool
    description: str


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
    cron: str | None
    recommended_cron: str
    schedule_ok: bool  # the configured schedule fires within the required cadence
    schedule_gap_days: int | None  # largest gap between scheduled runs, if any
