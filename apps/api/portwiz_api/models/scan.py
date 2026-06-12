"""Scanning models: scan profiles, scan runs, and observations.

Observations are the raw time-series of (host, port, service) seen by a scan.
They live in a TimescaleDB hypertable so scan history stays fast at scale and
feeds the flapping-aware change detection in M3.
"""

from __future__ import annotations

import datetime as dt
import enum
import uuid

from sqlalchemy import JSON, Column, DateTime, Float, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel


def _utcnow() -> dt.datetime:
    return dt.datetime.now(tz=dt.timezone.utc)


def _json_column() -> Column:
    return Column(JSON().with_variant(JSONB(), "postgresql"), nullable=False)


class ScanType(str, enum.Enum):
    syn = "syn"
    connect = "connect"
    udp = "udp"


class ScanSource(str, enum.Enum):
    internal_authenticated = "internal-authenticated"
    internal_unauthenticated = "internal-unauthenticated"
    external_asv = "external-asv"


class ScanRunStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    partial = "partial"
    failed = "failed"


class ScanProfile(SQLModel, table=True):
    __tablename__ = "scan_profiles"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str = Field(sa_column=Column(String(128), index=True, nullable=False))
    targets: list[str] = Field(default_factory=list, sa_column=_json_column())
    ports: str = Field(
        default="top-1000",
        sa_column=Column(String(128), nullable=False, server_default="top-1000"),
    )
    scan_type: ScanType = Field(
        default=ScanType.connect,
        sa_column=Column(String(16), nullable=False, server_default=ScanType.connect.value),
    )
    service_detection: bool = Field(default=True, nullable=False)
    rate_limit_pps: int = Field(
        default=1000, sa_column=Column(Integer, nullable=False, server_default="1000")
    )
    scan_source: ScanSource = Field(
        default=ScanSource.internal_unauthenticated,
        sa_column=Column(
            String(32),
            nullable=False,
            server_default=ScanSource.internal_unauthenticated.value,
        ),
    )
    # Cron expression for scheduled runs (scheduling itself lands in M5).
    cron: str | None = Field(default=None, sa_column=Column(String(64)))
    enabled: bool = Field(default=True, nullable=False)
    created_by: uuid.UUID | None = Field(default=None, foreign_key="users.id")
    created_at: dt.datetime = Field(
        default_factory=_utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_at: dt.datetime = Field(
        default_factory=_utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class ScanRun(SQLModel, table=True):
    __tablename__ = "scan_runs"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    scan_profile_id: uuid.UUID | None = Field(
        default=None, foreign_key="scan_profiles.id"
    )
    agent_id: str | None = Field(default=None, sa_column=Column(String(128)))
    status: ScanRunStatus = Field(
        default=ScanRunStatus.pending,
        sa_column=Column(String(16), nullable=False, server_default=ScanRunStatus.pending.value),
    )
    scan_source: ScanSource = Field(
        default=ScanSource.internal_unauthenticated,
        sa_column=Column(String(32), nullable=False),
    )
    started_at: dt.datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True))
    )
    finished_at: dt.datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True))
    )
    error: str | None = None
    created_at: dt.datetime = Field(
        default_factory=_utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class Observation(SQLModel, table=True):
    __tablename__ = "observations"

    # Composite primary key (id, ts): TimescaleDB requires the partitioning
    # column (ts) to be part of every unique/primary key.
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    ts: dt.datetime = Field(
        sa_column=Column(DateTime(timezone=True), primary_key=True, nullable=False)
    )
    scan_run_id: uuid.UUID = Field(foreign_key="scan_runs.id", nullable=False)
    asset_id: uuid.UUID | None = Field(default=None, foreign_key="assets.id")
    ip: str = Field(sa_column=Column(String(45), nullable=False))
    port: int = Field(sa_column=Column(Integer, nullable=False))
    protocol: str = Field(sa_column=Column(String(8), nullable=False))
    state: str = Field(sa_column=Column(String(16), nullable=False))
    service: str | None = Field(default=None, sa_column=Column(String(128)))
    version: str | None = Field(default=None, sa_column=Column(String(256)))
    product: str | None = Field(default=None, sa_column=Column(String(256)))
    banner_sha256: str | None = Field(default=None, sa_column=Column(String(64)))
    fingerprint_confidence: float | None = Field(default=None, sa_column=Column(Float))
