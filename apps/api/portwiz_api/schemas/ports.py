"""Schemas for the current open-port observability view."""

from __future__ import annotations

import datetime as dt
import uuid

from pydantic import BaseModel


class OpenPortRead(BaseModel):
    """A port confirmed open right now on a host, joined to its asset."""

    ip: str
    port: int
    protocol: str
    service: str | None
    version: str | None
    last_seen_open_at: dt.datetime | None
    asset_id: uuid.UUID | None
    hostname: str | None
    criticality: str | None
    suppressed: bool = False
