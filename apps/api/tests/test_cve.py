"""Unit tests for the CVE source (NVD parsing and gating)."""

from __future__ import annotations

import httpx

from portwiz_api.core.cve import (
    NullCVESource,
    NvdSource,
    build_cve_source,
    severity_from_cvss,
)

_NVD_RESPONSE = {
    "vulnerabilities": [
        {
            "cve": {
                "id": "CVE-2024-7347",
                "descriptions": [
                    {"lang": "es", "value": "otro"},
                    {"lang": "en", "value": "A buffer overflow in nginx."},
                ],
                "metrics": {
                    "cvssMetricV31": [{"cvssData": {"baseScore": 7.5}}],
                },
            }
        },
        {
            "cve": {
                "id": "CVE-2024-0002",
                "descriptions": [{"lang": "en", "value": "Low severity issue."}],
                "metrics": {"cvssMetricV31": [{"cvssData": {"baseScore": 2.1}}]},
            }
        },
    ]
}


def _mock_client(captured: list[httpx.Request], body: dict) -> httpx.AsyncClient:
    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, json=body)

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def test_severity_from_cvss() -> None:
    assert severity_from_cvss(None) == "unknown"
    assert severity_from_cvss(9.8) == "critical"
    assert severity_from_cvss(7.5) == "high"
    assert severity_from_cvss(5.0) == "medium"
    assert severity_from_cvss(2.1) == "low"


async def test_nvd_lookup_parses_and_filters(monkeypatch) -> None:
    captured: list[httpx.Request] = []
    source = NvdSource(min_cvss=4.0)
    monkeypatch.setattr(source, "_client", lambda: _mock_client(captured, _NVD_RESPONSE))

    cves = await source.lookup("nginx", "1.24.0")

    # The 2.1 finding is below min_cvss=4.0 and is dropped.
    assert [c.cve_id for c in cves] == ["CVE-2024-7347"]
    c = cves[0]
    assert c.cvss == 7.5 and c.severity == "high"
    assert "buffer overflow" in c.summary.lower()  # English description chosen
    assert c.url.endswith("CVE-2024-7347")
    # The keyword combines product + version.
    assert captured[0].url.params.get("keywordSearch") == "nginx 1.24.0"


async def test_nvd_lookup_empty_product() -> None:
    source = NvdSource()
    assert await source.lookup("", "1.0") == []


class _S:
    cve_enabled = True
    cve_source = "nvd"
    cve_api_url = ""
    cve_api_key = None
    cve_min_cvss = 0.0


def test_build_returns_null_when_disabled() -> None:
    s = _S()
    s.cve_enabled = False
    assert isinstance(build_cve_source(s), NullCVESource)


def test_build_returns_nvd_when_enabled() -> None:
    assert isinstance(build_cve_source(_S()), NvdSource)
