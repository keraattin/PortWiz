"""Request/response schemas for the asset inventory (VLAN, IPRange, Asset)."""

from __future__ import annotations

import datetime as dt
import ipaddress
import uuid

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ..models.asset import Criticality, DataSensitivity


def _validate_ip(value: str) -> str:
    ipaddress.ip_address(value)  # raises ValueError if invalid
    return value


def _validate_cidr(value: str) -> str:
    ipaddress.ip_network(value, strict=False)  # raises ValueError if invalid
    return value


# VLAN
class VLANCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    vlan_tag: int | None = Field(default=None, ge=1, le=4094)
    description: str | None = None


class VLANUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    vlan_tag: int | None = Field(default=None, ge=1, le=4094)
    description: str | None = None


class VLANRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    vlan_tag: int | None
    description: str | None
    created_at: dt.datetime


# IPRange
class IPRangeCreate(BaseModel):
    cidr: str
    vlan_id: uuid.UUID | None = None
    description: str | None = None

    @field_validator("cidr")
    @classmethod
    def _cidr(cls, v: str) -> str:
        return _validate_cidr(v)


class IPRangeUpdate(BaseModel):
    cidr: str | None = None
    vlan_id: uuid.UUID | None = None
    description: str | None = None

    @field_validator("cidr")
    @classmethod
    def _cidr(cls, v: str | None) -> str | None:
        return _validate_cidr(v) if v is not None else v


class IPRangeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    cidr: str
    vlan_id: uuid.UUID | None
    description: str | None
    created_at: dt.datetime


# Asset
class AssetCreate(BaseModel):
    ip: str
    hostname: str | None = Field(default=None, max_length=255)
    vlan_id: uuid.UUID | None = None
    owner_id: uuid.UUID | None = None
    criticality: Criticality = Criticality.medium
    data_sensitivity: DataSensitivity = DataSensitivity.none
    description: str | None = None

    @field_validator("ip")
    @classmethod
    def _ip(cls, v: str) -> str:
        return _validate_ip(v)


class AssetUpdate(BaseModel):
    ip: str | None = None
    hostname: str | None = Field(default=None, max_length=255)
    vlan_id: uuid.UUID | None = None
    owner_id: uuid.UUID | None = None
    criticality: Criticality | None = None
    data_sensitivity: DataSensitivity | None = None
    description: str | None = None

    @field_validator("ip")
    @classmethod
    def _ip(cls, v: str | None) -> str | None:
        return _validate_ip(v) if v is not None else v


class AssetRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    ip: str
    hostname: str | None
    vlan_id: uuid.UUID | None
    owner_id: uuid.UUID | None
    criticality: Criticality
    data_sensitivity: DataSensitivity
    description: str | None
    created_at: dt.datetime
    updated_at: dt.datetime


# Bulk import
class AssetImportRowResult(BaseModel):
    row: int  # 1-based row number in the source file
    ip: str | None = None
    status: str  # created | updated | skipped | error
    error: str | None = None


class AssetImportReport(BaseModel):
    total: int
    created: int
    updated: int
    skipped: int
    errors: int
    results: list[AssetImportRowResult]


class VLANImportRowResult(BaseModel):
    row: int
    name: str | None = None
    status: str  # created | updated | skipped | error
    error: str | None = None


class VLANImportReport(BaseModel):
    total: int
    created: int
    updated: int
    skipped: int
    errors: int
    results: list[VLANImportRowResult]


class AssetSyncReport(BaseModel):
    source: str
    total: int
    created: int
    updated: int
    skipped: int
    errors: int
    errors_detail: list[str]
