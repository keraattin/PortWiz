"""CVE enrichment: look up known vulnerabilities for a discovered service+version.

A provider-agnostic ``CVESource`` so other backends (an offline NVD feed, CIRCL
cve-search, a private vuln DB) can be added behind the same interface. Online
sources need outbound access and are disabled until configured. CVE data is
authoritative from the source, never invented; the AI layer only summarises or
prioritises what a source returns.
"""

from __future__ import annotations

import datetime as dt
import logging
from dataclasses import dataclass
from typing import Any, Protocol

import httpx
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from .db import get_session

logger = logging.getLogger("portwiz.cve")

_DEFAULT_NVD_URL = "https://services.nvd.nist.gov/rest/json/cves/2.0"


def _utcnow() -> dt.datetime:
    return dt.datetime.now(tz=dt.timezone.utc)


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


class OfflineNvdSource:
    """CVE lookups against a locally imported NVD feed, so enrichment works with
    no outbound access (air-gapped installs). Matching mirrors the online keyword
    search: a CVE matches when its stored text contains the product (and version).
    The upstream NVD data is downloaded elsewhere and uploaded via /cve/import."""

    name = "offline"

    def __init__(self, session: AsyncSession, min_cvss: float = 0.0, max_results: int = 20) -> None:
        self._session = session
        self._min = min_cvss
        self._max = max_results

    @staticmethod
    def _like(term: str) -> str:
        # Escape LIKE wildcards so a product like "net_snmp" matches literally.
        return term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")

    async def lookup(self, product: str, version: str | None) -> list[CVE]:
        # Match on the product name only. NVD encodes which versions are affected
        # in structured CPE ranges (versionStartIncluding/EndExcluding), not in
        # free text, so a substring version filter would wrongly drop range-based
        # CVEs. We return the product's highest-CVSS CVEs (bounded); an analyst
        # confirms version applicability, as with the online keyword search.
        from sqlalchemy import select

        from ..models.cve import CveRecord

        product = (product or "").strip().lower()
        if not product:
            return []
        stmt = select(CveRecord).where(
            CveRecord.search_text.like(f"%{self._like(product)}%", escape="\\")
        )
        if self._min > 0:
            stmt = stmt.where(CveRecord.cvss.is_not(None), CveRecord.cvss >= self._min)
        stmt = stmt.order_by(CveRecord.cvss.desc()).limit(self._max)
        rows = (await self._session.execute(stmt)).scalars().all()
        return [
            CVE(
                cve_id=r.cve_id,
                cvss=r.cvss,
                severity=r.severity,
                summary=r.summary[:500],
                url=r.url or f"https://nvd.nist.gov/vuln/detail/{r.cve_id}",
            )
            for r in rows
        ]

    async def verify(self) -> tuple[bool, str]:
        from sqlalchemy import func, select

        from ..models.cve import CveRecord

        count = (
            await self._session.execute(select(func.count()).select_from(CveRecord))
        ).scalar_one()
        if not count:
            return False, "No offline CVE data imported yet. Upload an NVD feed file."
        return True, f"{count} CVEs loaded from the offline feed."


async def import_nvd_feed(session: AsyncSession, content: bytes) -> dict[str, int]:
    """Parse an uploaded NVD 2.0 feed and upsert it into the local store (by CVE
    id). Returns ``{"total", "imported"}``. Processed in chunks so a large feed
    does not build one huge statement."""
    from sqlalchemy import select

    from ..models.cve import CveRecord
    from .nvd_feed import parse_nvd_feed

    records = parse_nvd_feed(content)
    now = _utcnow()
    imported = 0
    chunk = 500
    for start in range(0, len(records), chunk):
        batch = records[start : start + chunk]
        existing = {
            row.cve_id: row
            for row in (
                await session.execute(
                    select(CveRecord).where(CveRecord.cve_id.in_([r.cve_id for r in batch]))
                )
            ).scalars()
        }
        for r in batch:
            row = existing.get(r.cve_id)
            if row is None:
                session.add(
                    CveRecord(
                        cve_id=r.cve_id,
                        cvss=r.cvss,
                        severity=r.severity,
                        summary=r.summary,
                        url=r.url,
                        published=r.published,
                        search_text=r.search_text,
                        imported_at=now,
                    )
                )
            else:
                row.cvss = r.cvss
                row.severity = r.severity
                row.summary = r.summary
                row.url = r.url
                row.published = r.published
                row.search_text = r.search_text
                row.imported_at = now
            imported += 1
        await session.flush()
    await session.commit()
    return {"total": len(records), "imported": imported}


def build_cve_source(settings, session: AsyncSession | None = None) -> CVESource:
    """Return the configured CVE source, or a no-op when disabled.

    The offline source needs a database session for its lookups; without one it
    degrades to the null source so callers on the network-only path still work.
    """
    if not settings.cve_enabled:
        return NullCVESource()
    if settings.cve_source == "offline":
        if session is None:
            return NullCVESource()
        return OfflineNvdSource(session, min_cvss=settings.cve_min_cvss)
    return NvdSource(
        api_url=settings.cve_api_url,
        api_key=settings.cve_api_key,
        min_cvss=settings.cve_min_cvss,
    )


async def get_cve_source(session: AsyncSession = Depends(get_session)) -> CVESource:
    from .app_settings import effective_settings

    return build_cve_source(await effective_settings(session), session)


# Service labels too generic to yield precise CVEs on their own. Looking up a
# bare "http" or "https" (no product, no version) returns thousands of unrelated
# advisories, which is noise for an audit tool, so a port known only by one of
# these is skipped unless it also carries a product or version.
_GENERIC_SERVICES = frozenset(
    {
        "http",
        "https",
        "http-proxy",
        "https-alt",
        "http-alt",
        "ssl",
        "tls",
        "www",
        "unknown",
        "tcpwrapped",
    }
)


def _cve_target(product: str | None, service: str | None, version: str | None) -> str | None:
    """The product/service string to search CVEs for, or ``None`` when the port
    is too generic to yield precise findings.

    A named product (nmap's ``OpenSSH``, ``nginx``) is always specific enough. A
    bare service is used when it is either version-qualified or a distinctive
    product-like name (``redis``, ``mysql``); a generic protocol label alone
    (``http``) is skipped to keep findings precise.
    """
    prod = (product or "").strip()
    if prod:
        return prod
    svc = (service or "").strip()
    if svc and (version or svc.lower() not in _GENERIC_SERVICES):
        return svc
    return None


async def recheck_cves(
    session: AsyncSession, source: CVESource, limit: int = 25
) -> dict[str, int]:
    """Re-compute CVE findings for the current open ports with an identified
    service, whether or not a change was detected and whether or not a version is
    known.

    Uses the latest observation per (ip, port) that carries a product, service,
    or version, looks each up against the source, and replaces that port's
    findings. Ports known only by a generic protocol label (a bare ``http`` with
    no product or version) are skipped so findings stay precise. Bounded by
    ``limit`` because online sources are rate-limited; a lookup that errors (e.g.
    a rate-limit hit) is skipped so a partial re-check still records what it can.
    """
    from sqlalchemy import delete, or_, select

    from ..models.cve import CVEFinding
    from ..models.scan import Observation

    rows = (
        await session.execute(
            select(Observation)
            .where(
                Observation.state == "open",
                or_(
                    Observation.product.is_not(None),
                    Observation.service.is_not(None),
                    Observation.version.is_not(None),
                ),
            )
            .order_by(Observation.ts.desc())
            .limit(2000)
        )
    ).scalars().all()

    latest: dict[tuple[str, int], Observation] = {}
    for obs in rows:
        latest.setdefault((obs.ip, obs.port), obs)

    checked = findings = 0
    for obs in list(latest.values())[: max(0, limit)]:
        product = _cve_target(obs.product, obs.service, obs.version)
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
