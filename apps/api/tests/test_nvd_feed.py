"""Tests for the NVD 2.0 feed parser (offline CVE import)."""

from __future__ import annotations

import gzip
import json

import pytest

from portwiz_api.core.nvd_feed import parse_nvd_feed

_FEED = {
    "vulnerabilities": [
        {
            "cve": {
                "id": "CVE-2021-1234",
                "published": "2021-10-05T14:15:08.163",
                "descriptions": [
                    {"lang": "en", "value": "Apache HTTP Server path traversal flaw."}
                ],
                "metrics": {"cvssMetricV31": [{"cvssData": {"baseScore": 9.8}}]},
                "configurations": [
                    {"nodes": [{"cpeMatch": [{"criteria": "cpe:2.3:a:apache:http_server:2.4.49"}]}]}
                ],
            }
        },
        {
            "cve": {
                "id": "CVE-2020-0001",
                "descriptions": [{"lang": "en", "value": "OpenSSH minor issue."}],
                "metrics": {"cvssMetricV2": [{"cvssData": {"baseScore": 3.5}}]},
                "configurations": [
                    {"nodes": [{"cpeMatch": [{"criteria": "cpe:2.3:a:openbsd:openssh:8.0"}]}]}
                ],
            }
        },
    ]
}


def _bytes() -> bytes:
    return json.dumps(_FEED).encode()


def test_parse_extracts_records() -> None:
    by_id = {r.cve_id: r for r in parse_nvd_feed(_bytes())}
    assert set(by_id) == {"CVE-2021-1234", "CVE-2020-0001"}
    a = by_id["CVE-2021-1234"]
    assert a.cvss == 9.8
    assert a.severity == "critical"
    assert a.published is not None
    assert a.url.endswith("CVE-2021-1234")
    # search_text carries the description and the CPE vendor/product tokens
    # (underscores become spaces) so a service-name keyword lookup finds it.
    assert "apache" in a.search_text
    assert "http server" in a.search_text


def test_parse_accepts_gzip() -> None:
    assert len(parse_nvd_feed(gzip.compress(_bytes()))) == 2


def test_parse_accepts_bare_list() -> None:
    assert len(parse_nvd_feed(json.dumps(_FEED["vulnerabilities"]).encode())) == 2


def test_parse_rejects_bad_input() -> None:
    with pytest.raises(ValueError):
        parse_nvd_feed(b"not json at all")
    with pytest.raises(ValueError):
        parse_nvd_feed(json.dumps({"unexpected": 1}).encode())
