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
    discovered: bool
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
    cidr: str | None = None  # the IP range attached on this row, if any
    status: str  # created | updated | skipped | error
    error: str | None = None


class VLANImportReport(BaseModel):
    total: int
    created: int
    updated: int
    skipped: int
    errors: int
    # IP ranges attached from the same file (VLAN + its ranges import as one unit).
    ranges_created: int = 0
    ranges_skipped: int = 0
    results: list[VLANImportRowResult]


class AssetSyncReport(BaseModel):
    source: str
    total: int
    created: int
    updated: int
    skipped: int
    errors: int
    errors_detail: list[str]


# Bulk operations (assistant "add/delete several at once"), keyed by IP.
class AssetBulkItem(BaseModel):
    ip: str
    hostname: str | None = Field(default=None, max_length=255)
    criticality: Criticality = Criticality.medium
    data_sensitivity: DataSensitivity = DataSensitivity.none


class AssetBulkCreate(BaseModel):
    items: list[AssetBulkItem]


class AssetBulkDelete(BaseModel):
    ips: list[str]


class AssetBulkUpdate(BaseModel):
    ips: list[str]
    # Only the fields that are set are applied to every listed asset; omitted
    # fields are left untouched (this cannot clear an owner/VLAN, only set one).
    criticality: Criticality | None = None
    data_sensitivity: DataSensitivity | None = None
    owner_id: uuid.UUID | None = None
    vlan_id: uuid.UUID | None = None


class AssetBulkReport(BaseModel):
    total: int
    succeeded: int  # created (bulk create) or deleted (bulk delete)
    skipped: int  # already existed (create) / not found (delete)
    errors: int
    errors_detail: list[str]


# Shared bulk-operation report for VLANs and IP ranges (same shape as assets).
class BulkReport(BaseModel):
    total: int
    succeeded: int  # created or deleted
    skipped: int  # already existed / not found
    errors: int
    errors_detail: list[str]


class VlanBulkItem(BaseModel):
    name: str
    vlan_tag: int | None = None
    description: str | None = None


class VlanBulkCreate(BaseModel):
    items: list[VlanBulkItem]


class VlanBulkDelete(BaseModel):
    names: list[str]


class VlanBulkUpdate(BaseModel):
    # By id (the UI selects specific rows); only set fields are applied.
    ids: list[uuid.UUID]
    description: str | None = None


class IPRangeBulkItem(BaseModel):
    cidr: str
    vlan_name: str | None = None
    description: str | None = None


class IPRangeBulkCreate(BaseModel):
    items: list[IPRangeBulkItem]


class IPRangeBulkDelete(BaseModel):
    cidrs: list[str]


class IPRangeBulkUpdate(BaseModel):
    ids: list[uuid.UUID]
    vlan_id: uuid.UUID | None = None
    description: str | None = None


class VlanSyncReport(BaseModel):
    source: str
    total: int
    created: int
    updated: int
    skipped: int
    errors: int
    errors_detail: list[str]


class IPRangeSyncReport(BaseModel):
    source: str
    total: int
    created: int
    updated: int
    skipped: int
    errors: int
    errors_detail: list[str]


class AssetPushReport(BaseModel):
    source: str
    total: int  # discovered assets considered for writeback
    created: int
    skipped: int
    errors: int
    errors_detail: list[str]


# Interactive sync: preview what the source offers, then apply a chosen subset
# with per-import attributes set in the staging UI.
class AssetPreviewItem(BaseModel):
    ip: str
    hostname: str | None = None
    exists: bool  # already an asset in PortWiz


class AssetSyncApplyItem(BaseModel):
    ip: str
    hostname: str | None = None
    criticality: Criticality | None = None
    data_sensitivity: DataSensitivity | None = None
    owner_id: uuid.UUID | None = None
    vlan_id: uuid.UUID | None = None


class AssetSyncApply(BaseModel):
    items: list[AssetSyncApplyItem]
