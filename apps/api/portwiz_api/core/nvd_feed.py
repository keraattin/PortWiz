"""Parse an NVD 2.0 JSON feed into local CVE records for offline lookups.

Air-gapped installs cannot reach the NVD API, so an admin downloads NVD data on
a connected machine and uploads it here. This module reduces an uploaded file
(plain ``.json`` or gzipped ``.json.gz``) to normalized records, reusing the same
NVD 2.0 field extraction as the online source so offline and online agree.

Parsing is database-free so it is cheap to unit-test; the route does the upsert.
The expected shape is an NVD API 2.0 response: ``{"vulnerabilities": [{"cve":
{...}}]}`` (a bare list of ``cve`` objects is also accepted).
"""

from __future__ import annotations

import datetime as dt
import gzip
import json
from dataclasses import dataclass
from typing import Any

from .cve import _best_cvss, _english_desc, severity_from_cvss


@dataclass
class FeedRecord:
    cve_id: str
    cvss: float | None
    severity: str
    summary: str
    url: str
    published: dt.datetime | None
    search_text: str


def _parse_published(value: Any) -> dt.datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _cpe_tokens(cve: dict[str, Any]) -> str:
    """Vendor/product names from the CVE's CPE matches, so a keyword lookup on a
    service name finds it even when the description does not spell it out."""
    tokens: set[str] = set()
    for conf in cve.get("configurations", []) or []:
        for node in conf.get("nodes", []) or []:
            for match in node.get("cpeMatch", []) or []:
                # cpe:2.3:a:{vendor}:{product}:{version}:...
                parts = str(match.get("criteria", "")).split(":")
                if len(parts) > 4:
                    tokens.add(parts[3].replace("_", " "))  # vendor
                    tokens.add(parts[4].replace("_", " "))  # product
    tokens.discard("")
    tokens.discard("*")
    return " ".join(sorted(tokens))


def _decode(content: bytes) -> Any:
    # Gzip magic bytes: transparently accept .json.gz feed files.
    if content[:2] == b"\x1f\x8b":
        content = gzip.decompress(content)
    return json.loads(content)


def parse_nvd_feed(content: bytes) -> list[FeedRecord]:
    """Parse an NVD 2.0 feed (plain or gzipped) into records. Raises ValueError
    for a file-level problem (not JSON, or an unrecognized shape)."""
    try:
        data = _decode(content)
    except (OSError, ValueError) as exc:  # gzip/json errors
        raise ValueError(f"Could not read the feed: {exc}") from exc

    if isinstance(data, dict) and "vulnerabilities" in data:
        items = data["vulnerabilities"]
    elif isinstance(data, list):
        items = data
    else:
        raise ValueError("Unrecognized feed format. Expected NVD API 2.0 JSON.")

    records: list[FeedRecord] = []
    for item in items:
        cve = item.get("cve", item) if isinstance(item, dict) else {}
        cve_id = cve.get("id")
        if not cve_id:
            continue
        score = _best_cvss(cve)
        summary = _english_desc(cve)
        search_text = f"{summary} {_cpe_tokens(cve)}".lower()
        records.append(
            FeedRecord(
                cve_id=cve_id,
                cvss=score,
                severity=severity_from_cvss(score),
                summary=summary[:500],
                url=f"https://nvd.nist.gov/vuln/detail/{cve_id}",
                published=_parse_published(cve.get("published")),
                search_text=search_text,
            )
        )
    return records
