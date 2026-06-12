"""Validation tests for inventory schemas (IP/CIDR shape, VLAN tag bounds)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from portwiz_api.schemas.asset import AssetCreate, IPRangeCreate, VLANCreate


def test_asset_accepts_valid_ipv4_and_ipv6() -> None:
    assert AssetCreate(ip="10.0.0.5").ip == "10.0.0.5"
    assert AssetCreate(ip="2001:db8::1").ip == "2001:db8::1"


def test_asset_rejects_invalid_ip() -> None:
    with pytest.raises(ValidationError):
        AssetCreate(ip="not-an-ip")
    with pytest.raises(ValidationError):
        AssetCreate(ip="10.0.0.999")


def test_ip_range_accepts_valid_cidr() -> None:
    assert IPRangeCreate(cidr="10.0.0.0/24").cidr == "10.0.0.0/24"


def test_ip_range_rejects_invalid_cidr() -> None:
    with pytest.raises(ValidationError):
        IPRangeCreate(cidr="10.0.0.0/99")


def test_vlan_tag_bounds() -> None:
    assert VLANCreate(name="dmz", vlan_tag=4094).vlan_tag == 4094
    with pytest.raises(ValidationError):
        VLANCreate(name="bad", vlan_tag=5000)
    with pytest.raises(ValidationError):
        VLANCreate(name="bad", vlan_tag=0)
