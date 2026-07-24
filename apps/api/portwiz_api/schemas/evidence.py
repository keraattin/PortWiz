"""Schema for a one-click auditor evidence package."""

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel

from .audit import ChainVerification
from .change import ChangeEventRead
from .cve import CVEFindingRead
from .scan import ScanProfileRead, ScanRunRead


class OpenPort(BaseModel):
    ip: str
    port: int
    protocol: str
    service: str | None
    version: str | None
    last_seen_open_at: dt.datetime | None


class EvidencePackage(BaseModel):
    generated_at: dt.datetime
    generated_by: str
    profile: ScanProfileRead
    chain_verification: ChainVerification
    current_open_ports: list[OpenPort]
    cve_findings: list[CVEFindingRead]
    scan_runs: list[ScanRunRead]
    changes: list[ChangeEventRead]
