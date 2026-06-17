"""Schema for the dashboard overview."""

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel


class DashboardStats(BaseModel):
    assets: int
    vlans: int
    agents_total: int
    agents_online: int
    open_changes: int
    open_tasks: int
    pending_runs: int
    last_scan_at: dt.datetime | None


class TimePoint(BaseModel):
    date: str  # ISO date (YYYY-MM-DD)
    count: int


class Slice(BaseModel):
    name: str
    value: int


class DashboardCharts(BaseModel):
    changes_by_day: list[TimePoint]
    changes_by_type: list[Slice]
    assets_by_criticality: list[Slice]
    runs_by_status: list[Slice]
    compliance_by_status: list[Slice]
