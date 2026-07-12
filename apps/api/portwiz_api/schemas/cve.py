"""Schemas for CVE findings."""

from __future__ import annotations

import datetime as dt
import uuid

from pydantic import BaseModel, ConfigDict


class CVEFindingRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    asset_id: uuid.UUID | None
    ip: str
    port: int
    protocol: str
    service: str | None
    version: str | None
    cve_id: str
    cvss: float | None
    severity: str
    summary: str
    url: str
    source: str
    detected_at: dt.datetime


class CVERecheckResult(BaseModel):
    checked: int
    findings: int


class CVEImportReport(BaseModel):
    total: int  # CVE entries found in the uploaded feed
    imported: int  # entries stored (created or updated)
    loaded: int  # total CVEs now in the offline store


class CVESummary(BaseModel):
    provider: str
    count: int  # number of real findings the brief was built from
    summary: str
