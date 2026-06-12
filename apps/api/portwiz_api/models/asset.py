"""Asset inventory models: VLANs, IP ranges, and assets.

These form the compliance inventory (NIST CM-8, ISO 27001 A.8.1): every asset
carries an owner, a criticality, and a data-sensitivity classification so scans
and changes can be scoped and attributed.
"""

from __future__ import annotations

import datetime as dt
import enum
import uuid

from sqlalchemy import Column, DateTime, Integer, String
from sqlmodel import Field, SQLModel


def _utcnow() -> dt.datetime:
    return dt.datetime.now(tz=dt.timezone.utc)


class Criticality(str, enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class DataSensitivity(str, enum.Enum):
    none = "none"
    pii = "pii"
    cde = "cde"  # PCI cardholder data environment
    ephi = "ephi"  # HIPAA electronic protected health information


class VLAN(SQLModel, table=True):
    __tablename__ = "vlans"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str = Field(
        sa_column=Column(String(128), unique=True, index=True, nullable=False)
    )
    vlan_tag: int | None = Field(default=None, sa_column=Column(Integer))
    description: str | None = None
    created_at: dt.datetime = Field(
        default_factory=_utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class IPRange(SQLModel, table=True):
    __tablename__ = "ip_ranges"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    cidr: str = Field(sa_column=Column(String(64), index=True, nullable=False))
    vlan_id: uuid.UUID | None = Field(default=None, foreign_key="vlans.id")
    description: str | None = None
    created_at: dt.datetime = Field(
        default_factory=_utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class Asset(SQLModel, table=True):
    __tablename__ = "assets"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    ip: str = Field(sa_column=Column(String(45), index=True, nullable=False))
    hostname: str | None = Field(default=None, sa_column=Column(String(255)))
    vlan_id: uuid.UUID | None = Field(default=None, foreign_key="vlans.id")
    owner_id: uuid.UUID | None = Field(default=None, foreign_key="users.id")
    criticality: Criticality = Field(
        default=Criticality.medium,
        sa_column=Column(String(16), nullable=False, server_default=Criticality.medium.value),
    )
    data_sensitivity: DataSensitivity = Field(
        default=DataSensitivity.none,
        sa_column=Column(String(16), nullable=False, server_default=DataSensitivity.none.value),
    )
    description: str | None = None
    created_at: dt.datetime = Field(
        default_factory=_utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_at: dt.datetime = Field(
        default_factory=_utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
