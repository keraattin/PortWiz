"""CVE enrichment: look up known vulnerabilities for a discovered service+version.

A provider-agnostic ``CVESource`` so other backends (an offline NVD feed, CIRCL
cve-search, a private vuln DB) can be added behind the same interface. Online
sources need outbound access and are disabled until configured. CVE data is
authoritative from the source, never invented; the AI layer only summarises or
prioritises what a source returns.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Protocol

import httpx
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from .db import get_session

logger = logging.getLogger("portwiz.cve")

_DEFAULT_NVD_URL = "https://services.nvd.nist.gov/rest/json/cves/2.0"


@dataclass
class CVE:
    cve_id: str
    cvss: float | None
    severity: str  # critical | high | medium | low | unknown
    summary: str
    url: str


def severity_from_cvss(score: float | None) -> str:
    if score is None:
        return "unknown"
    if score >= 9.0:
        return "critical"
    if score >= 7.0:
        return "high"
    if score >= 4.0:
        return "medium"
    return "low"


class CVESource(Protocol):
    name: str

    async def lookup(self, product: str, version: str | None) -> list[CVE]: ...
    async def verify(self) -> tuple[bool, str]: ...


class NullCVESource:
    """Used when CVE enrichment is not configured. Every lookup is empty."""

    name = "none"

    async def lookup(self, product: str, version: str | None) -> list[CVE]:
        return []

    async def verify(self) -> tuple[bool, str]:
        return False, "CVE enrichment is not configured."


def _best_cvss(cve: dict[str, Any]) -> float | None:
    metrics = cve.get("metrics", {})
    for key in ("cvssMetricV31", "cvssMetricV30", "cvssMetricV2"):
        arr = metrics.get(key)
        if arr:
            try:
                return float(arr[0]["cvssData"]["baseScore"])
            except (KeyError, IndexError, TypeError, ValueError):
                continue
    return None


def _english_desc(cve: dict[str, Any]) -> str:
    for d in cve.get("descriptions", []):
        if d.get("lang") == "en":
            return d.get("value", "")
    descriptions = cve.get("descriptions", [])
    return descriptions[0].get("value", "") if descriptions else ""


class NvdSource:
    """NVD 2.0 keyword search. Best-effort: it matches CVEs whose text mentions
    the product and version, so it favours precision over completeness (a CVE
    described only by a version range may be missed). An API key raises the
    rate limit from 5 to 50 requests per 30 seconds."""

    name = "nvd"

    def __init__(
        self,
        api_url: str = "",
        api_key: str | None = None,
        min_cvss: float = 0.0,
        max_results: int = 20,
    ) -> None:
        self._url = (api_url or _DEFAULT_NVD_URL).rstrip("/")
        self._key = (api_key or "").strip() or None
        self._min = min_cvss
        self._max = max_results

    def _headers(self) -> dict[str, str]:
        return {"apiKey": self._key} if self._key else {}

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(timeout=20)

    async def lookup(self, product: str, version: str | None) -> list[CVE]:
        product = (product or "").strip()
        if not product:
            return []
        keyword = f"{product} {version}".strip() if version else product
        params: dict[str, Any] = {"keywordSearch": keyword, "resultsPerPage": self._max}
        async with self._client() as client:
            resp = await client.get(self._url, params=params, headers=self._headers())
            resp.raise_for_status()
            data = resp.json()

        findings: list[CVE] = []
        for item in data.get("vulnerabilities", []):
            cve = item.get("cve", {})
            cid = cve.get("id")
            if not cid:
                continue
            score = _best_cvss(cve)
            if score is not None and score < self._min:
                continue
            findings.append(
                CVE(
                    cve_id=cid,
                    cvss=score,
                    severity=severity_from_cvss(score),
                    summary=_english_desc(cve)[:500],
                    url=f"https://nvd.nist.gov/vuln/detail/{cid}",
                )
            )
        return findings

    async def verify(self) -> tuple[bool, str]:
        try:
            async with self._client() as client:
                resp = await client.get(
                    self._url, params={"resultsPerPage": 1}, headers=self._headers()
                )
                resp.raise_for_status()
            return True, "Connected to the NVD API."
        except Exception as exc:  # surface any connectivity/rate-limit failure
            return False, str(exc)


def build_cve_source(settings) -> CVESource:
    """Return the configured CVE source, or a no-op when disabled."""
    if not settings.cve_enabled:
        return NullCVESource()
    # Only NVD is implemented today; the ``cve_source`` switch reserves room for
    # an offline feed / CIRCL behind the same interface.
    return NvdSource(
        api_url=settings.cve_api_url,
        api_key=settings.cve_api_key,
        min_cvss=settings.cve_min_cvss,
    )


async def get_cve_source(session: AsyncSession = Depends(get_session)) -> CVESource:
    from .app_settings import effective_settings

    return build_cve_source(await effective_settings(session))


async def recheck_cves(
    session: AsyncSession, source: CVESource, limit: int = 25
) -> dict[str, int]:
    """Re-compute CVE findings for the current open ports that carry a version.

    Uses the latest observation per (ip, port) with a known version, looks each
    up against the source, and replaces that port's findings. Bounded by
    ``limit`` because online sources are rate-limited; a lookup that errors (e.g.
    a rate-limit hit) is skipped so a partial re-check still records what it can.
    """
    from sqlalchemy import delete, select

    from ..models.cve import CVEFinding
    from ..models.scan import Observation

    rows = (
        await session.execute(
            select(Observation)
            .where(Observation.version.is_not(None), Observation.state == "open")
            .order_by(Observation.ts.desc())
            .limit(2000)
        )
    ).scalars().all()

    latest: dict[tuple[str, int], Observation] = {}
    for obs in rows:
        latest.setdefault((obs.ip, obs.port), obs)

    checked = findings = 0
    for obs in list(latest.values())[: max(0, limit)]:
        product = (obs.product or obs.service or "").strip()
        if not product:
            continue
        try:
            cves = await source.lookup(product, obs.version)
        except Exception as exc:  # rate limit / network: skip this one, keep going
            logger.warning("CVE lookup failed for %s:%s (%s): %s", obs.ip, obs.port, product, exc)
            continue
        checked += 1
        await session.execute(
            delete(CVEFinding).where(CVEFinding.ip == obs.ip, CVEFinding.port == obs.port)
        )
        for c in cves:
            session.add(
                CVEFinding(
                    asset_id=obs.asset_id,
                    ip=obs.ip,
                    port=obs.port,
                    protocol=obs.protocol,
                    service=obs.service,
                    version=obs.version,
                    cve_id=c.cve_id,
                    cvss=c.cvss,
                    severity=c.severity,
                    summary=c.summary,
                    url=c.url,
                    source=source.name,
                )
            )
            findings += 1
    await session.commit()
    return {"checked": checked, "findings": findings}
