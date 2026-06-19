"""Unit tests for the VLAN import parser (no DB)."""

from __future__ import annotations

import pytest

from portwiz_api.core.vlan_import import parse_vlan_file


def test_parse_vlan_csv() -> None:
    content = b"name,tag,description\nDMZ,10,edge\nServers,20,\n"
    rows = parse_vlan_file(content, "vlans.csv")
    assert len(rows) == 2
    assert rows[0].values["name"] == "DMZ"
    assert rows[0].values["tag"] == "10"
    assert rows[0].values["description"] == "edge"
    assert rows[0].error is None
    assert rows[1].values["name"] == "Servers"
    assert "description" not in rows[1].values  # blank cells are dropped


def test_parse_vlan_aliases_and_tag_validation() -> None:
    # 'vlan' aliases name; 'vlan tag' aliases tag; a 10.0 spreadsheet float is ok.
    content = b"vlan,vlan tag\nOffice,30.0\nBad,5000\n,10\n"
    rows = parse_vlan_file(content, "vlans.csv")
    assert rows[0].values["name"] == "Office" and rows[0].values["tag"] == "30"
    assert rows[1].error and "range" in rows[1].error.lower()
    assert rows[2].error and "name" in rows[2].error.lower()


def test_parse_vlan_missing_name_column() -> None:
    with pytest.raises(ValueError):
        parse_vlan_file(b"tag,description\n10,x\n", "vlans.csv")
