"""Bulk VLAN import from CSV and Excel files.

Mirrors :mod:`asset_import`: a CSV or .xlsx upload is reduced to a string matrix,
headers (with common aliases) are mapped to canonical fields, and each row is
validated structurally (name required, tag in range). The upsert by name happens
in the route, where the database is available. Parsing is database-free so it is
cheap to unit-test; openpyxl is imported lazily.
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field

# Canonical field -> accepted header spellings (lowercased, trimmed).
_HEADER_ALIASES: dict[str, set[str]] = {
    "name": {"name", "vlan", "vlan name", "label"},
    "tag": {"tag", "vlan tag", "vlan_tag", "vlan id", "802.1q", "dot1q"},
    "description": {"description", "desc", "notes"},
}

_HEADER_LOOKUP = {alias: field for field, aliases in _HEADER_ALIASES.items() for alias in aliases}


@dataclass
class ParsedRow:
    """One data row from the upload. ``error`` is set when the row is invalid."""

    row: int  # 1-based position in the source file (the header is row 1)
    values: dict[str, str] = field(default_factory=dict)
    error: str | None = None


def _canonical_header(cell: str) -> str | None:
    return _HEADER_LOOKUP.get(str(cell).strip().lower())


def _read_matrix(content: bytes, filename: str) -> list[list[str]]:
    """Reduce a CSV or .xlsx upload to a matrix of trimmed string cells."""
    name = filename.lower()
    if name.endswith(".csv"):
        text = content.decode("utf-8-sig", errors="replace")
        return [[str(c) for c in row] for row in csv.reader(io.StringIO(text))]
    if name.endswith((".xlsx", ".xlsm")):
        import openpyxl

        workbook = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True)
        try:
            sheet = workbook.active
            matrix: list[list[str]] = []
            for row in sheet.iter_rows(values_only=True):
                matrix.append(["" if cell is None else str(cell) for cell in row])
            return matrix
        finally:
            workbook.close()
    raise ValueError("Unsupported file type. Use a .csv or .xlsx file.")


def _validate_values(values: dict[str, str]) -> tuple[dict[str, str], str | None]:
    if not values.get("name"):
        return values, "Missing VLAN name"
    if "tag" in values:
        raw = values["tag"]
        try:
            tag = int(float(raw))  # tolerate "10.0" from spreadsheets
        except (TypeError, ValueError):
            return values, f"Invalid VLAN tag '{raw}'"
        if not 1 <= tag <= 4094:
            return values, f"VLAN tag out of range (1-4094): '{raw}'"
        values["tag"] = str(tag)
    return values, None


def parse_vlan_file(content: bytes, filename: str) -> list[ParsedRow]:
    """Parse an upload into rows. Raises ValueError for a file-level problem
    (unsupported type, empty file, or a missing ``name`` column)."""
    matrix = _read_matrix(content, filename)

    header_idx = next(
        (i for i, row in enumerate(matrix) if any(str(c).strip() for c in row)),
        None,
    )
    if header_idx is None:
        raise ValueError("File is empty.")

    headers = [_canonical_header(c) for c in matrix[header_idx]]
    if "name" not in headers:
        raise ValueError("Missing required 'name' column.")

    rows: list[ParsedRow] = []
    for offset in range(header_idx + 1, len(matrix)):
        raw = matrix[offset]
        if not any(str(c).strip() for c in raw):
            continue  # skip blank lines
        values: dict[str, str] = {}
        for col, cell in zip(headers, raw, strict=False):
            if col is None:
                continue
            text = str(cell).strip()
            if text:
                values[col] = text
        cleaned, error = _validate_values(values)
        rows.append(ParsedRow(row=offset + 1, values=cleaned, error=error))
    return rows
