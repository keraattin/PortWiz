"""Change-detection models: per-port confirmed state and confirmed changes.

PortState is the flapping-aware state machine: it tracks the confirmed state of
each (profile, host, port) plus a pending "candidate" state and how many
consecutive runs have shown it. A change is only emitted as a ChangeEvent once
the candidate has been seen CONFIRMATIONS times in a row, which filters out
network jitter.
"""

from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import JSON, Column, DateTime, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel


def _utcnow() -> dt.datetime:
    return dt.datetime.now(tz=dt.timezone.utc)


def _json_column(nullable: bool = False) -> Column:
    return Column(JSON().with_variant(JSONB(), "postgresql"), nullable=nullable)


class PortState(SQLModel, table=True):
    __tablename__ = "port_states"
    __table_args__ = (
        UniqueConstraint(
            "scan_profile_id", "ip", "port", "protocol", name="uq_port_state_key"
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    scan_profile_id: uuid.UUID = Field(foreign_key="scan_profiles.id", nullable=False)
    ip: str = Field(sa_column=Column(String(45), nullable=False))
    port: int = Field(sa_column=Column(Integer, nullable=False))
    protocol: str = Field(sa_column=Column(String(8), nullable=False))

    confirmed_state: str = Field(sa_column=Column(String(8), nullable=False))
    confirmed_service: str | None = Field(default=None, sa_column=Column(String(128)))
    confirmed_version: str | None = Field(default=None, sa_column=Column(String(256)))

    candidate_state: str | None = Field(default=None, sa_column=Column(String(8)))
    candidate_service: str | None = Field(default=None, sa_column=Column(String(128)))
    candidate_version: str | None = Field(default=None, sa_column=Column(String(256)))
    candidate_count: int = Field(default=0, nullable=False)

    last_seen_open_at: dt.datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True))
    )
    updated_at: dt.datetime = Field(
        default_factory=_utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class ChangeEvent(SQLModel, table=True):
    __tablename__ = "change_events"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    scan_profile_id: uuid.UUID = Field(foreign_key="scan_profiles.id", nullable=False)
    scan_run_id: uuid.UUID | None = Field(default=None, foreign_key="scan_runs.id")
    asset_id: uuid.UUID | None = Field(default=None, foreign_key="assets.id")

    ip: str = Field(sa_column=Column(String(45), index=True, nullable=False))
    port: int = Field(sa_column=Column(Integer, nullable=False))
    protocol: str = Field(sa_column=Column(String(8), nullable=False))

    # opened | closed | service_changed | version_changed
    change_type: str = Field(sa_column=Column(String(32), index=True, nullable=False))
    before: dict = Field(default_factory=dict, sa_column=_json_column())
    after: dict = Field(default_factory=dict, sa_column=_json_column())
    severity: str = Field(sa_column=Column(String(16), nullable=False))
    # open | acknowledged | resolved
    status: str = Field(
        default="open",
        sa_column=Column(String(16), nullable=False, server_default="open", index=True),
    )
    detected_at: dt.datetime = Field(
        default_factory=_utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
