"""Schemas for the TLS certificate expiry view."""

from __future__ import annotations

import datetime as dt
import uuid

from pydantic import BaseModel


class CertificateRead(BaseModel):
    ip: str
    port: int
    protocol: str
    asset_id: uuid.UUID | None
    hostname: str | None
    subject_cn: str | None
    issuer: str | None
    sans: list[str] | None
    not_before: dt.datetime | None
    not_after: dt.datetime | None
    self_signed: bool | None
    serial: str | None
    sig_alg: str | None
    days_to_expiry: int | None
    status: str  # expired | expiring | valid
