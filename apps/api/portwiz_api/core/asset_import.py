"""Bulk asset import from CSV and Excel files.

Reading hundreds of assets into the inventory by hand is a non-starter, so this
module parses a CSV or .xlsx upload into normalized rows. Both formats are
reduced to a common string matrix, then a single parser maps headers (with
common aliases) to canonical fields and validates each row structurally (IP and
enum values). Reference resolution (VLAN name, owner email) and the upsert
happen in the route, where the database is available.

Parsing is deliberately database-free so it is cheap to unit-test. openpyxl is
imported lazily so a CSV-only path never loads it.
"""

from __future__ import annotations

import csv
import io
import ipaddress
from dataclasses import dataclass, field

from ..models.asset import Criticality, DataSensitivity

_CRITICALITIES = {c.value for c in Criticality}
_SENSITIVITIES = {s.value for s in DataSensitivity}

# Canonical field -> accepted header spellings (lowercased, trimmed).
_HEADER_ALIASES: dict[str, set[str]] = {
    "ip": {"ip", "ip address", "ipaddress", "address"},
    "hostname": {"hostname", "host", "host name", "name"},
    "vlan": {"vlan", "vlan name", "segment"},
    "owner": {"owner", "owner email", "owner_email", "email"},
    "criticality": {"criticality", "crit"},
    "data_sensitivity": {
        "data sensitivity",
        "data_sensitivity",
        "sensitivity",
        "classification",
    },
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
        # utf-8-sig tolerates the BOM that Excel prepends to CSV exports.
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
    ip = values.get("ip", "")
    if not ip:
        return values, "Missing IP address"
    try:
        ipaddress.ip_address(ip)
    except ValueError:
        return values, f"Invalid IP address '{ip}'"

    if "criticality" in values:
        crit = values["criticality"].lower()
        if crit not in _CRITICALITIES:
            return values, f"Invalid criticality '{values['criticality']}'"
        values["criticality"] = crit

    if "data_sensitivity" in values:
        sens = values["data_sensitivity"].lower()
        if sens not in _SENSITIVITIES:
            return values, f"Invalid data sensitivity '{values['data_sensitivity']}'"
        values["data_sensitivity"] = sens

    return values, None


def parse_asset_file(content: bytes, filename: str) -> list[ParsedRow]:
    """Parse an upload into rows. Raises ValueError for a file-level problem
    (unsupported type, empty file, or a missing ``ip`` column)."""
    matrix = _read_matrix(content, filename)

    header_idx = next(
        (i for i, row in enumerate(matrix) if any(str(c).strip() for c in row)),
        None,
    )
    if header_idx is None:
        raise ValueError("File is empty.")

    headers = [_canonical_header(c) for c in matrix[header_idx]]
    if "ip" not in headers:
        raise ValueError("Missing required 'ip' column.")

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
