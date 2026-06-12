"""Validation tests for scan profile schemas."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from portwiz_api.schemas.scan import ScanProfileCreate


def test_valid_profile_defaults() -> None:
    profile = ScanProfileCreate(name="weekly", targets=["10.0.0.0/24", "192.168.1.5"])
    assert profile.ports == "top-1000"
    assert profile.scan_type.value == "connect"
    assert profile.scan_source.value == "internal-unauthenticated"
    assert profile.rate_limit_pps == 1000


def test_empty_targets_rejected() -> None:
    with pytest.raises(ValidationError):
        ScanProfileCreate(name="x", targets=[])


def test_invalid_target_rejected() -> None:
    with pytest.raises(ValidationError):
        ScanProfileCreate(name="x", targets=["not-a-cidr!!"])


def test_rate_limit_bounds() -> None:
    with pytest.raises(ValidationError):
        ScanProfileCreate(name="x", targets=["10.0.0.1"], rate_limit_pps=0)
    with pytest.raises(ValidationError):
        ScanProfileCreate(name="x", targets=["10.0.0.1"], rate_limit_pps=200_000)
