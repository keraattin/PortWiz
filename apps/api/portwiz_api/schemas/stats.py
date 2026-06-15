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
