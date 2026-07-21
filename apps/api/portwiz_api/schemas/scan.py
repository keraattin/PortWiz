"""Schemas for scan profiles, scan runs, and observations."""

from __future__ import annotations

import datetime as dt
import ipaddress
import uuid

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ..models.scan import ComplianceFramework, ScanRunStatus, ScanSource, ScanType


def _validate_targets(targets: list[str]) -> list[str]:
    if not targets:
        raise ValueError("at least one target is required")
    for target in targets:
        try:
            ipaddress.ip_network(target, strict=False)
        except ValueError as exc:
            raise ValueError(f"invalid target '{target}': expected an IP or CIDR") from exc
    return targets


def _validate_cron(cron: str | None) -> str | None:
    """Reject a malformed cron up front. Without this a bad expression is stored
    and simply never fires (the scheduler skips invalid crons silently), so the
    profile looks scheduled but never runs."""
    if cron is None or cron == "":
        return None
    from croniter import croniter

    if not croniter.is_valid(cron):
        raise ValueError(f"invalid cron expression: '{cron}'")
    return cron


# ScanProfile
class ScanProfileCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    targets: list[str]
    ports: str = Field(default="top-1000", min_length=1, max_length=128)
    scan_type: ScanType = ScanType.connect
    service_detection: bool = True
    rate_limit_pps: int = Field(default=1000, ge=1, le=100000)
    scan_source: ScanSource = ScanSource.internal_unauthenticated
    segment: str | None = Field(default=None, max_length=64)
    compliance_framework: ComplianceFramework | None = None
    cron: str | None = Field(default=None, max_length=64)
    enabled: bool = True
    notify_enabled: bool = True

    @field_validator("targets")
    @classmethod
    def _targets(cls, v: list[str]) -> list[str]:
        return _validate_targets(v)

    @field_validator("cron")
    @classmethod
    def _cron(cls, v: str | None) -> str | None:
        return _validate_cron(v)


class ScanProfileUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    targets: list[str] | None = None
    ports: str | None = Field(default=None, min_length=1, max_length=128)
    scan_type: ScanType | None = None
    service_detection: bool | None = None
    rate_limit_pps: int | None = Field(default=None, ge=1, le=100000)
    scan_source: ScanSource | None = None
    segment: str | None = Field(default=None, max_length=64)
    compliance_framework: ComplianceFramework | None = None
    cron: str | None = Field(default=None, max_length=64)
    enabled: bool | None = None
    notify_enabled: bool | None = None

    @field_validator("targets")
    @classmethod
    def _targets(cls, v: list[str] | None) -> list[str] | None:
        return _validate_targets(v) if v is not None else v

    @field_validator("cron")
    @classmethod
    def _cron(cls, v: str | None) -> str | None:
        return _validate_cron(v)


class ScanProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    targets: list[str]
    ports: str
    scan_type: ScanType
    service_detection: bool
    rate_limit_pps: int
    scan_source: ScanSource
    segment: str | None
    compliance_framework: ComplianceFramework | None
    cron: str | None
    last_scheduled_at: dt.datetime | None
    enabled: bool
    notify_enabled: bool
    created_by: uuid.UUID | None
    created_at: dt.datetime
    updated_at: dt.datetime


# ScanRun
class ScanRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    scan_profile_id: uuid.UUID | None
    agent_id: str | None
    status: ScanRunStatus
    scan_source: ScanSource
    started_at: dt.datetime | None
    finished_at: dt.datetime | None
    error: str | None
    created_at: dt.datetime


# Scan job dispatched to an agent (mirrors packages/contracts/scan_job.schema.json)
class ScanJobOut(BaseModel):
    version: int = 1
    job_id: uuid.UUID
    scan_run_id: uuid.UUID
    scan_profile_id: uuid.UUID | None
    targets: list[str]
    ports: str
    scan_type: ScanType
    service_detection: bool
    rate_limit_pps: int
    scan_source: ScanSource


# Scan result ingest (mirrors packages/contracts/scan_result.schema.json)
class PortIn(BaseModel):
    port: int = Field(ge=1, le=65535)
    protocol: str = Field(pattern="^(tcp|udp)$")
    state: str = Field(pattern="^(open|closed|filtered)$")
    service: str | None = None
    version: str | None = None
    product: str | None = None
    # Banner is attacker-influenced free text; bound it so a compromised agent
    # can't push megabytes per port (it is only hashed and optionally enriched).
    banner: str | None = Field(default=None, max_length=8192)
    banner_sha256: str | None = None
    fingerprint_confidence: float | None = Field(default=None, ge=0, le=1)


class HostIn(BaseModel):
    ip: str
    hostname: str | None = Field(default=None, max_length=253)
    # At most one entry per TCP port; caps per-host observation writes.
    ports: list[PortIn] = Field(max_length=65536)


class ScanResultIn(BaseModel):
    version: int = 1
    job_id: uuid.UUID
    scan_run_id: uuid.UUID
    agent_id: str
    started_at: dt.datetime
    finished_at: dt.datetime
    status: str = Field(default="completed", pattern="^(completed|partial|failed)$")
    error: str | None = None
    # Bound a single ingest to a /16 worth of hosts; larger scans must chunk.
    # Stops an unbounded payload from driving huge memory/DB writes.
    hosts: list[HostIn] = Field(max_length=65536)


# Observation
class ObservationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    ts: dt.datetime
    scan_run_id: uuid.UUID
    asset_id: uuid.UUID | None
    ip: str
    port: int
    protocol: str
    state: str
    service: str | None
    version: str | None
    product: str | None
    banner_sha256: str | None
    fingerprint_confidence: float | None
    fingerprint_source: str | None
