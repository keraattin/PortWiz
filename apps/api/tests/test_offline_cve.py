"""Tests for the offline NVD CVE source (import + lookup + source switch)."""

from __future__ import annotations

import json

from portwiz_api.core.config import get_settings
from portwiz_api.core.cve import (
    NullCVESource,
    NvdSource,
    OfflineNvdSource,
    build_cve_source,
    import_nvd_feed,
)

_FEED = {
    "vulnerabilities": [
        {
            "cve": {
                "id": "CVE-2021-1234",
                "descriptions": [{"lang": "en", "value": "Apache HTTP Server flaw."}],
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
                    {"nodes": [{"cpeMatch": [{"criteria": "cpe:2.3:a:openbsd:openssh:8.0:*"}]}]}
                ],
            }
        },
    ]
}


def _content() -> bytes:
    return json.dumps(_FEED).encode()


async def test_import_and_lookup(db) -> None:
    async with db() as session:
        result = await import_nvd_feed(session, _content())
        assert result == {"total": 2, "imported": 2}

    async with db() as session:
        src = OfflineNvdSource(session)
        # A version is passed (as the recheck does) but matching is product-based.
        hits = await src.lookup("apache", "2.4.49")
        assert [c.cve_id for c in hits] == ["CVE-2021-1234"]
        assert hits[0].severity == "critical"
        assert [c.cve_id for c in await src.lookup("openssh", None)] == ["CVE-2020-0001"]
        assert await src.lookup("nonexistent-product", None) == []
        ok, msg = await src.verify()
        assert ok and "2" in msg


async def test_import_is_upsert(db) -> None:
    from sqlalchemy import func, select

    from portwiz_api.models.cve import CveRecord

    async with db() as session:
        await import_nvd_feed(session, _content())
        assert (await import_nvd_feed(session, _content()))["imported"] == 2
    async with db() as session:
        count = (await session.execute(select(func.count()).select_from(CveRecord))).scalar_one()
        assert count == 2  # re-import upserts, never duplicates


async def test_min_cvss_filters(db) -> None:
    async with db() as session:
        await import_nvd_feed(session, _content())
    async with db() as session:
        src = OfflineNvdSource(session, min_cvss=7.0)
        assert await src.lookup("openssh", None) == []  # 3.5 is below the floor
        assert [c.cve_id for c in await src.lookup("apache", None)] == ["CVE-2021-1234"]


async def test_verify_empty_store(db) -> None:
    async with db() as session:
        ok, msg = await OfflineNvdSource(session).verify()
        assert ok is False and "import" in msg.lower()


def test_build_cve_source_switch() -> None:
    offline = get_settings().model_copy(update={"cve_enabled": True, "cve_source": "offline"})
    # Offline needs a session; without one it degrades to the null source.
    assert isinstance(build_cve_source(offline, None), NullCVESource)
    assert build_cve_source(offline, session=object()).name == "offline"
    # The default path is still the online NVD source.
    online = get_settings().model_copy(update={"cve_enabled": True, "cve_source": "nvd"})
    assert isinstance(build_cve_source(online), NvdSource)
    # Disabled always yields the null source.
    disabled = get_settings().model_copy(update={"cve_enabled": False})
    assert isinstance(build_cve_source(disabled), NullCVESource)
