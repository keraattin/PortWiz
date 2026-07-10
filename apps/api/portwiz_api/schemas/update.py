"""Schema for the update-availability check."""

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel


class UpdateStatusRead(BaseModel):
    enabled: bool  # whether the check is turned on
    current: str  # running version
    latest: str | None  # newest published version, if known
    update_available: bool
    url: str | None  # release notes / releases page
    checked_at: dt.datetime | None
    error: str | None
    apply_available: bool  # one-click apply possible (updater sidecar deployed)
