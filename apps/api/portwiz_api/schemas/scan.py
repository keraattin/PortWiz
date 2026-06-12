"""Schemas for scan profiles, scan runs, and observations."""

from __future__ import annotations

import datetime as dt
import ipaddress
import uuid

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ..models.scan import ScanRunStatus, ScanSource, ScanType


def _validate_targets(targets: list[str]) -> list[str]:
    if not targets:
        raise ValueError("at least one target is required")
    for target in targets:
        try:
            ipaddress.ip_network(target, strict=False)
        except ValueError as exc:
            raise ValueError(f"invalid target '{target}': expected an IP or CIDR") from exc
    return targets


# ScanProfile
class ScanProfileCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    targets: list[str]
    ports: str = Field(default="top-1000", min_length=1, max_length=128)
    scan_type: ScanType = ScanType.connect
    service_detection: bool = True
    rate_limit_pps: int = Field(default=1000, ge=1, le=100000)
    scan_source: ScanSource = ScanSource.internal_unauthenticated
    cron: str | None = Field(default=None, max_length=64)
    enabled: bool = True

    @field_validator("targets")
    @classmethod
    def _targets(cls, v: list[str]) -> list[str]:
        return _validate_targets(v)


class ScanProfileUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    targets: list[str] | None = None
    ports: str | None = Field(default=None, min_length=1, max_length=128)
    scan_type: ScanType | None = None
    service_detection: bool | None = None
    rate_limit_pps: int | None = Field(default=None, ge=1, le=100000)
    scan_source: ScanSource | None = None
    cron: str | None = Field(default=None, max_length=64)
    enabled: bool | None = None

    @field_validator("targets")
    @classmethod
    def _targets(cls, v: list[str] | None) -> list[str] | None:
        return _validate_targets(v) if v is not None else v


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
    cron: str | None
    enabled: bool
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


# Scan result ingest (mirrors packages/contracts/scan_result.schema.json)
class PortIn(BaseModel):
    port: int = Field(ge=1, le=65535)
    protocol: str = Field(pattern="^(tcp|udp)$")
    state: str = Field(pattern="^(open|closed|filtered)$")
    service: str | None = None
    version: str | None = None
    product: str | None = None
    banner: str | None = None
    banner_sha256: str | None = None
    fingerprint_confidence: float | None = Field(default=None, ge=0, le=1)


class HostIn(BaseModel):
    ip: str
    hostname: str | None = None
    ports: list[PortIn]


class ScanResultIn(BaseModel):
    version: int = 1
    job_id: uuid.UUID
    scan_run_id: uuid.UUID
    agent_id: str
    started_at: dt.datetime
    finished_at: dt.datetime
    status: str = Field(default="completed", pattern="^(completed|partial|failed)$")
    error: str | None = None
    hosts: list[HostIn]


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
