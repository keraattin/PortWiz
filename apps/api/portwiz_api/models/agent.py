"""Scan agent model.

Agents are the distributed scanners deployed per VLAN/segment. Each enrolls
once and authenticates to the ingest endpoint with a bearer token; only the
SHA-256 hash of that token is stored.
"""

from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import Column, DateTime, String
from sqlmodel import Field, SQLModel


def _utcnow() -> dt.datetime:
    return dt.datetime.now(tz=dt.timezone.utc)


class Agent(SQLModel, table=True):
    __tablename__ = "agents"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str = Field(
        sa_column=Column(String(128), unique=True, index=True, nullable=False)
    )
    token_hash: str = Field(
        sa_column=Column(String(64), unique=True, index=True, nullable=False)
    )
    # Network segment this agent scans. Runs are routed to an agent whose segment
    # matches the scan profile's segment (a null segment matches null profiles).
    segment: str | None = Field(default=None, sa_column=Column(String(64), index=True))
    enabled: bool = Field(default=True, nullable=False)
    last_seen_at: dt.datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True))
    )
    # Self-reported by the agent on each heartbeat; last_ip is observed by the
    # server from the request (respecting a reverse proxy's forwarded header).
    version: str | None = Field(default=None, sa_column=Column(String(32)))
    platform: str | None = Field(default=None, sa_column=Column(String(64)))
    last_ip: str | None = Field(default=None, sa_column=Column(String(45)))
    # Set whenever the bearer token is regenerated, so the UI can surface how
    # long the current credential has been in use.
    token_rotated_at: dt.datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True))
    )
    created_at: dt.datetime = Field(
        default_factory=_utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
