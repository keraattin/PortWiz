"""Scan result ingest.

Agents POST a ScanResult here. The control plane normalizes the timestamp to
its own receive time (avoiding agent clock skew), writes one Observation per
open port, maps observed IPs to known assets, and finalizes the ScanRun.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.app_settings import effective_settings
from ...core.audit import append_audit
from ...core.change_detection import detect_changes
from ...core.db import get_session
from ...core.issue_tracker import IssueTracker, get_issue_tracker, link_changes_to_tracker
from ...core.notifications import build_notifier, notify_changes
from ...models.agent import Agent
from ...models.asset import Asset
from ...models.scan import Observation, ScanRun, ScanRunStatus
from ...schemas.scan import ScanResultIn
from ..deps import get_current_agent

logger = logging.getLogger("portwiz.ingest")
router = APIRouter(prefix="/ingest", tags=["ingest"])

_FINALIZED = {ScanRunStatus.completed, ScanRunStatus.failed}


def _utcnow() -> dt.datetime:
    return dt.datetime.now(tz=dt.timezone.utc)


@router.post("/scan-results", status_code=status.HTTP_202_ACCEPTED)
async def ingest_scan_results(
    payload: ScanResultIn,
    agent: Agent = Depends(get_current_agent),
    session: AsyncSession = Depends(get_session),
    tracker: IssueTracker = Depends(get_issue_tracker),
) -> dict[str, object]:
    run = await session.get(ScanRun, payload.scan_run_id)
    if run is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Scan run not found")
    if run.status in _FINALIZED:
        raise HTTPException(status.HTTP_409_CONFLICT, "Scan run already finalized")

    received_at = _utcnow()

    # Map observed IPs to known assets for enrichment.
    observed_ips = {host.ip for host in payload.hosts}
    asset_map: dict[str, object] = {}
    if observed_ips:
        rows = (
            await session.execute(
                select(Asset.id, Asset.ip).where(Asset.ip.in_(observed_ips))
            )
        ).all()
        asset_map = {ip: asset_id for asset_id, ip in rows}

    count = 0
    for host in payload.hosts:
        for port in host.ports:
            banner_hash = port.banner_sha256
            if banner_hash is None and port.banner is not None:
                banner_hash = hashlib.sha256(port.banner.encode("utf-8")).hexdigest()
            session.add(
                Observation(
                    ts=received_at,
                    scan_run_id=run.id,
                    asset_id=asset_map.get(host.ip),
                    ip=host.ip,
                    port=port.port,
                    protocol=port.protocol,
                    state=port.state,
                    service=port.service,
                    version=port.version,
                    product=port.product,
                    banner_sha256=banner_hash,
                    fingerprint_confidence=port.fingerprint_confidence,
                )
            )
            count += 1

    run.status = ScanRunStatus(payload.status)
    run.started_at = run.started_at or payload.started_at
    run.finished_at = received_at
    run.agent_id = str(agent.id)
    agent.last_seen_at = received_at

    # Flush observations so change detection can read them, then run it.
    await session.flush()
    changes = await detect_changes(session, run)
    change_summaries = [
        {
            "change_type": c.change_type,
            "ip": c.ip,
            "port": c.port,
            "protocol": c.protocol,
            "severity": c.severity,
        }
        for c in changes
    ]

    await append_audit(
        session,
        action="scan_run.ingested",
        actor_email=f"agent:{agent.name}",
        target_type="scan_run",
        target_id=str(run.id),
        payload={
            "agent": agent.name,
            "observations": count,
            "status": payload.status,
            "changes": len(changes),
        },
    )
    await session.commit()

    # Best-effort notification: never fail ingest if email delivery fails.
    if change_summaries:
        eff = await effective_settings(session)
        try:
            await notify_changes(
                change_summaries, eff.notification_recipients, build_notifier(eff)
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("change notification failed: %s", exc)

    # Best-effort issue-tracker sync (creates Jira issues for the new tasks).
    if changes:
        try:
            await link_changes_to_tracker(session, changes, tracker)
        except Exception as exc:  # noqa: BLE001
            logger.warning("issue tracker sync failed: %s", exc)

    return {
        "scan_run_id": str(run.id),
        "observations": count,
        "status": payload.status,
        "changes": len(changes),
    }
