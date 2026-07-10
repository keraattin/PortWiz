"""Tests for compliance cadence status."""

from __future__ import annotations

import datetime as dt

from portwiz_api.core.compliance import cadence_status

_NOW = dt.datetime(2026, 6, 17, 12, 0, 0, tzinfo=dt.timezone.utc)


def test_cadence_status_buckets() -> None:
    assert cadence_status(90, None) == "never"
    assert cadence_status(90, 10) == "compliant"
    assert cadence_status(90, 80) == "due_soon"  # > 85% of 90
    assert cadence_status(90, 120) == "overdue"


def test_max_cron_gap_days() -> None:
    from portwiz_api.core.compliance import max_cron_gap_days

    assert max_cron_gap_days(None) is None
    assert max_cron_gap_days("not a cron") is None
    assert max_cron_gap_days("0 3 1 * *") == 31  # monthly: worst gap is a 31-day month
    assert max_cron_gap_days("0 3 1 */3 *") == 92  # quarterly: worst gap 92 days
    assert max_cron_gap_days("0 3 * * 1") == 7  # weekly
    assert max_cron_gap_days("0 3 * * *") == 1  # daily


def test_cron_meets_cadence() -> None:
    from portwiz_api.core.compliance import cron_meets_cadence

    # Monthly (31d worst gap) meets PCI's 90-day requirement.
    assert cron_meets_cadence("0 3 1 * *", 90) is True
    # Quarterly's 92-day worst gap BREACHES PCI's 90-day window...
    assert cron_meets_cadence("0 3 1 */3 *", 90) is False
    # ...but comfortably meets the 180/365-day frameworks.
    assert cron_meets_cadence("0 3 1 */3 *", 180) is True
    # No schedule never meets a cadence.
    assert cron_meets_cadence(None, 90) is False
    assert cron_meets_cadence("bogus", 365) is False


def test_framework_templates_recommended_meets_own_cadence() -> None:
    # Every recommended schedule must satisfy its own framework's requirement.
    from portwiz_api.core.compliance import FRAMEWORK_TEMPLATES, cron_meets_cadence

    for tpl in FRAMEWORK_TEMPLATES.values():
        assert cron_meets_cadence(tpl.recommended_cron, tpl.cadence_days), tpl.framework


async def _profile(db, *, framework, scan_source):
    from portwiz_api.models.scan import ScanProfile

    async with db() as session:
        profile = ScanProfile(
            name=f"{framework}-{scan_source.value}",
            targets=["10.0.0.1"],
            scan_source=scan_source,
            compliance_framework=framework,
        )
        session.add(profile)
        await session.commit()
        return profile.id


async def _add_run(db, profile_id, *, status, finished_at):
    from portwiz_api.models.scan import ScanRun, ScanSource

    async with db() as session:
        run = ScanRun(
            scan_profile_id=profile_id,
            scan_source=ScanSource.internal_unauthenticated,
            status=status,
            finished_at=finished_at,
        )
        session.add(run)
        await session.commit()


async def test_compliance_status_overdue_and_never(db) -> None:
    from portwiz_api.core.compliance import compliance_status
    from portwiz_api.models.scan import (
        ComplianceFramework,
        ScanRunStatus,
        ScanSource,
    )

    # PCI profile (90d) scanned 100 days ago -> overdue. Internal source -> ASV not satisfied.
    pid = await _profile(
        db, framework=ComplianceFramework.pci, scan_source=ScanSource.internal_unauthenticated
    )
    await _add_run(
        db, pid, status=ScanRunStatus.completed, finished_at=_NOW - dt.timedelta(days=100)
    )
    # HIPAA profile (180d) never scanned -> never.
    await _profile(
        db, framework=ComplianceFramework.hipaa, scan_source=ScanSource.internal_authenticated
    )

    async with db() as session:
        items = await compliance_status(session, now=_NOW)

    by_fw = {i["framework"]: i for i in items}
    assert by_fw["pci"]["status"] == "overdue"
    assert by_fw["pci"]["asv_satisfied"] is False  # internal scan, PCI needs ASV
    assert by_fw["hipaa"]["status"] == "never"
    assert by_fw["hipaa"]["asv_satisfied"] is True  # ASV not applicable


async def test_compliance_status_compliant_and_asv(db) -> None:
    from portwiz_api.core.compliance import compliance_status
    from portwiz_api.models.scan import ComplianceFramework, ScanRunStatus, ScanSource

    pid = await _profile(
        db, framework=ComplianceFramework.pci, scan_source=ScanSource.external_asv
    )
    await _add_run(
        db, pid, status=ScanRunStatus.completed, finished_at=_NOW - dt.timedelta(days=10)
    )
    async with db() as session:
        items = await compliance_status(session, now=_NOW)
    item = items[0]
    assert item["status"] == "compliant"
    assert item["asv_satisfied"] is True  # external-asv satisfies PCI


async def test_status_endpoint_requires_auth(client) -> None:
    assert (await client.get("/api/v1/compliance/status")).status_code == 401


async def test_status_endpoint_lists_framework_profiles(client, admin_headers) -> None:
    await client.post(
        "/api/v1/scan-profiles",
        json={"name": "pci-scan", "targets": ["10.0.0.1"], "compliance_framework": "pci"},
        headers=admin_headers,
    )
    # A profile without a framework is excluded.
    await client.post(
        "/api/v1/scan-profiles",
        json={"name": "plain", "targets": ["10.0.0.2"]},
        headers=admin_headers,
    )
    resp = await client.get("/api/v1/compliance/status", headers=admin_headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert len(body) == 1
    assert body[0]["framework"] == "pci"
    assert body[0]["status"] == "never"
    assert body[0]["cadence_days"] == 90


async def test_status_reports_schedule_adequacy(client, admin_headers) -> None:
    # No cron -> schedule is not OK; recommended cron is surfaced for the UI.
    await client.post(
        "/api/v1/scan-profiles",
        json={"name": "pci-noschedule", "targets": ["10.0.0.1"], "compliance_framework": "pci"},
        headers=admin_headers,
    )
    # Monthly cron meets PCI's 90-day cadence -> schedule OK.
    await client.post(
        "/api/v1/scan-profiles",
        json={
            "name": "pci-monthly",
            "targets": ["10.0.0.2"],
            "compliance_framework": "pci",
            "cron": "0 3 1 * *",
        },
        headers=admin_headers,
    )
    body = (await client.get("/api/v1/compliance/status", headers=admin_headers)).json()
    by_name = {i["profile_name"]: i for i in body}
    assert by_name["pci-noschedule"]["schedule_ok"] is False
    assert by_name["pci-noschedule"]["schedule_gap_days"] is None
    assert by_name["pci-noschedule"]["recommended_cron"] == "0 3 1 * *"
    assert by_name["pci-monthly"]["schedule_ok"] is True
    assert by_name["pci-monthly"]["schedule_gap_days"] == 31


async def test_frameworks_catalog_endpoint(client, admin_headers) -> None:
    resp = await client.get("/api/v1/compliance/frameworks", headers=admin_headers)
    assert resp.status_code == 200, resp.text
    by_fw = {f["framework"]: f for f in resp.json()}
    assert set(by_fw) == {"pci", "hipaa", "soc2", "iso27001", "nist"}
    assert by_fw["pci"]["cadence_days"] == 90
    assert by_fw["pci"]["requires_external_asv"] is True
    assert by_fw["pci"]["recommended_label"] == "monthly"
    assert by_fw["hipaa"]["requires_external_asv"] is False


async def test_frameworks_catalog_requires_auth(client) -> None:
    assert (await client.get("/api/v1/compliance/frameworks")).status_code == 401


async def test_create_profile_rejects_invalid_cron(client, admin_headers) -> None:
    resp = await client.post(
        "/api/v1/scan-profiles",
        json={"name": "bad-cron", "targets": ["10.0.0.1"], "cron": "not a cron"},
        headers=admin_headers,
    )
    assert resp.status_code == 422, resp.text
