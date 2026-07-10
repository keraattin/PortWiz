"""Schemas for scan agents."""

from __future__ import annotations

import datetime as dt
import uuid

from pydantic import BaseModel, ConfigDict, Field


class AgentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    segment: str | None = Field(default=None, max_length=64)


class AgentUpdate(BaseModel):
    segment: str | None = Field(default=None, max_length=64)
    enabled: bool | None = None
    # Per-agent overrides. A field sent as null clears the override (back to the
    # global setting); an omitted field is left unchanged. Positive values only.
    poll_seconds_override: int | None = Field(default=None, ge=1)
    online_seconds_override: int | None = Field(default=None, ge=1)
    rate_limit_pps_override: int | None = Field(default=None, ge=1)


class AgentHeartbeat(BaseModel):
    """Optional metadata an agent self-reports on each heartbeat."""

    version: str | None = Field(default=None, max_length=32)
    platform: str | None = Field(default=None, max_length=64)


class AgentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    segment: str | None
    enabled: bool
    last_seen_at: dt.datetime | None
    version: str | None
    platform: str | None
    last_ip: str | None
    token_rotated_at: dt.datetime | None
    poll_seconds_override: int | None
    online_seconds_override: int | None
    rate_limit_pps_override: int | None
    created_at: dt.datetime
    # Live status computed server-side: online | offline | never | disabled.
    status: str | None = None


class SegmentCoverageRead(BaseModel):
    segment: str | None  # None = the unsegmented pool
    agents_total: int
    agents_online: int
    profiles: int
    covered: bool


class FleetSummaryRead(BaseModel):
    """Fleet-wide status counts plus per-segment coverage and coverage gaps."""

    agents_total: int
    agents_online: int
    agents_offline: int
    agents_never_seen: int
    agents_disabled: int
    segments: list[SegmentCoverageRead]
    gaps: list[SegmentCoverageRead]  # segments with profiles but no online agent


class AgentCreated(BaseModel):
    """Returned once at enrollment; carries the plaintext token."""

    id: uuid.UUID
    name: str
    segment: str | None
    token: str
    created_at: dt.datetime


class AgentTokenRotated(BaseModel):
    """Returned once after a rotation; carries the new plaintext token."""

    id: uuid.UUID
    name: str
    token: str
    token_rotated_at: dt.datetime


class AgentConfig(BaseModel):
    """Effective operational config an agent fetches for itself (global setting
    overlaid with this agent's override). The agent applies poll_seconds."""

    poll_seconds: int
