"""CVE finding model: a known vulnerability matched to a discovered service.

Findings are (re)computed from a CVE source for the current open ports and
replaced per (ip, port) on each re-check, so the table reflects the latest
lookup rather than an ever-growing history.
"""

from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import Column, DateTime, Float, Integer, String, Text
from sqlmodel import Field, SQLModel


def _utcnow() -> dt.datetime:
    return dt.datetime.now(tz=dt.timezone.utc)


class CVEFinding(SQLModel, table=True):
    __tablename__ = "cve_findings"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    asset_id: uuid.UUID | None = Field(default=None, foreign_key="assets.id", index=True)
    ip: str = Field(sa_column=Column(String(45), index=True, nullable=False))
    port: int = Field(sa_column=Column(Integer, nullable=False))
    protocol: str = Field(sa_column=Column(String(8), nullable=False))
    # The service/version the CVE was matched against (for traceability).
    service: str | None = Field(default=None, sa_column=Column(String(128)))
    version: str | None = Field(default=None, sa_column=Column(String(256)))

    cve_id: str = Field(sa_column=Column(String(32), index=True, nullable=False))
    cvss: float | None = Field(default=None, sa_column=Column(Float))
    severity: str = Field(sa_column=Column(String(16), nullable=False))  # critical|high|...
    summary: str = Field(default="", sa_column=Column(Text, nullable=False))
    url: str = Field(default="", sa_column=Column(String(255), nullable=False))
    source: str = Field(sa_column=Column(String(32), nullable=False))  # nvd, ...

    detected_at: dt.datetime = Field(
        default_factory=_utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class CveRecord(SQLModel, table=True):
    """A single CVE from an imported NVD feed, stored locally so lookups work
    offline (air-gapped installs). Keyed by CVE id; ``search_text`` is a
    lowercased blob (description + affected vendor/product tokens) that the
    offline source keyword-matches a discovered service against."""

    __tablename__ = "cve_records"

    cve_id: str = Field(sa_column=Column(String(32), primary_key=True))
    cvss: float | None = Field(default=None, sa_column=Column(Float))
    severity: str = Field(sa_column=Column(String(16), nullable=False))  # critical|high|...
    summary: str = Field(default="", sa_column=Column(Text, nullable=False))
    url: str = Field(default="", sa_column=Column(String(255), nullable=False))
    published: dt.datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True))
    )
    # Lowercased description + affected vendor/product tokens, for keyword match.
    search_text: str = Field(default="", sa_column=Column(Text, nullable=False))
    imported_at: dt.datetime = Field(
        default_factory=_utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
