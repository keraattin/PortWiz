"""Unit tests for asset-import parsing (no DB, no network)."""

from __future__ import annotations

import io

import pytest

from portwiz_api.core.asset_import import parse_asset_file


def _csv(text: str) -> bytes:
    return text.encode("utf-8")


def test_parse_csv_happy_path() -> None:
    rows = parse_asset_file(
        _csv("ip,hostname,criticality\n10.0.0.5,web01,high\n10.0.0.6,,low\n"), "a.csv"
    )
    assert len(rows) == 2
    assert rows[0].error is None
    assert rows[0].values == {"ip": "10.0.0.5", "hostname": "web01", "criticality": "high"}
    # A blank cell is omitted entirely (not stored as "").
    assert rows[1].values == {"ip": "10.0.0.6", "criticality": "low"}


def test_header_aliases_and_bom() -> None:
    rows = parse_asset_file(_csv("﻿IP Address,Sensitivity\n10.0.0.5,cde\n"), "a.csv")
    assert rows[0].values["ip"] == "10.0.0.5"
    assert rows[0].values["data_sensitivity"] == "cde"


def test_unknown_columns_ignored() -> None:
    rows = parse_asset_file(_csv("ip,rack,note\n10.0.0.5,R1,hi\n"), "a.csv")
    assert rows[0].values == {"ip": "10.0.0.5"}


def test_invalid_ip_is_row_error() -> None:
    rows = parse_asset_file(_csv("ip\nnot-an-ip\n"), "a.csv")
    assert rows[0].error and "Invalid IP" in rows[0].error


def test_missing_ip_value_is_row_error() -> None:
    rows = parse_asset_file(_csv("ip,hostname\n,web01\n"), "a.csv")
    assert rows[0].error == "Missing IP address"


def test_invalid_enum_is_row_error() -> None:
    rows = parse_asset_file(_csv("ip,criticality\n10.0.0.5,banana\n"), "a.csv")
    assert rows[0].error and "Invalid criticality" in rows[0].error


def test_enum_is_lowercased() -> None:
    rows = parse_asset_file(_csv("ip,criticality\n10.0.0.5,HIGH\n"), "a.csv")
    assert rows[0].error is None
    assert rows[0].values["criticality"] == "high"


def test_blank_lines_skipped_with_correct_row_numbers() -> None:
    rows = parse_asset_file(_csv("ip\n10.0.0.5\n\n10.0.0.6\n"), "a.csv")
    assert [r.row for r in rows] == [2, 4]


def test_missing_ip_column_raises() -> None:
    with pytest.raises(ValueError, match="ip"):
        parse_asset_file(_csv("hostname\nweb01\n"), "a.csv")


def test_unsupported_type_raises() -> None:
    with pytest.raises(ValueError, match="Unsupported"):
        parse_asset_file(b"whatever", "a.txt")


def test_empty_file_raises() -> None:
    with pytest.raises(ValueError, match="empty"):
        parse_asset_file(b"", "a.csv")


def test_parse_xlsx() -> None:
    import openpyxl

    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.append(["ip", "hostname", "criticality"])
    sheet.append(["10.0.0.5", "web01", "high"])
    sheet.append(["10.0.0.6", None, None])
    buffer = io.BytesIO()
    workbook.save(buffer)

    rows = parse_asset_file(buffer.getvalue(), "assets.xlsx")
    assert len(rows) == 2
    assert rows[0].values == {"ip": "10.0.0.5", "hostname": "web01", "criticality": "high"}
    assert rows[1].values == {"ip": "10.0.0.6"}
