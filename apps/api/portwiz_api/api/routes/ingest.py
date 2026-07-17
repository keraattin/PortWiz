"""Scan result ingest.

Agents POST a ScanResult here. The control plane normalizes the timestamp to
its own receive time (avoiding agent clock skew), writes one Observation per
open port, maps observed IPs to known assets, and finalizes the ScanRun.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import hashlib
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.ai import (
    CONFIDENCE_FLOOR,
    AIProvider,
    enrich_fingerprint,
    get_ai_provider,
    parse_fingerprint_summary,
)
from ...core.app_settings import effective_settings
from ...core.audit import append_audit
from ...core.change_detection import detect_changes
from ...core.db import get_session
from ...core.fingerprint import match_banner
from ...core.inventory_source import (
    InventorySource,
    SourceAsset,
    get_inventory_source,
)
from ...core.issue_tracker import IssueTracker, get_issue_tracker, link_changes_to_tracker
from ...core.notifications import notify_changes
from ...models.agent import Agent
from ...models.asset import Asset, Criticality
from ...models.scan import Observation, ScanProfile, ScanRun, ScanRunStatus
from ...schemas.scan import ScanResultIn
from ..deps import get_current_agent

logger = logging.getLogger("portwiz.ingest")
router = APIRouter(prefix="/ingest", tags=["ingest"])

_FINALIZED = {ScanRunStatus.completed, ScanRunStatus.failed}

# AI fingerprint enrichment is best-effort and must never slow ingest much: only
# low-confidence banners are enriched, capped, concurrently, with a per-call
# timeout, before change detection so the run is compared on the refined values.
_MAX_ENRICH = 8
_ENRICH_TIMEOUT = 20.0


def _utcnow() -> dt.datetime:
    return dt.datetime.now(tz=dt.timezone.utc)


async def _enrich_observations(
    provider: AIProvider, candidates: list[tuple[Observation, str]]
) -> None:
    """Refine service/version on low-confidence observations via the AI provider.
    Each call is isolated: any failure or timeout leaves that observation as-is."""

    async def one(obs: Observation, banner: str) -> None:
        try:
            summary = await asyncio.wait_for(
                enrich_fingerprint(provider, banner, obs.port, obs.protocol, obs.service),
                timeout=_ENRICH_TIMEOUT,
            )
            service, version = parse_fingerprint_summary(summary)
            if service:
                obs.service = service
            if version:
                obs.version = version
            if service or version:
                obs.fingerprint_source = "ai"
        except Exception as exc:  # noqa: BLE001 - never fail ingest on enrichment
            logger.warning("AI fingerprint enrichment failed (%s): %s", provider.name, exc)

    await asyncio.gather(*(one(obs, banner) for obs, banner in candidates))


@router.post("/scan-results", status_code=status.HTTP_202_ACCEPTED)
async def ingest_scan_results(
    payload: ScanResultIn,
    agent: Agent = Depends(get_current_agent),
    session: AsyncSession = Depends(get_session),
    tracker: IssueTracker = Depends(get_issue_tracker),
    ai_provider: AIProvider = Depends(get_ai_provider),
    source: InventorySource = Depends(get_inventory_source),
) -> dict[str, object]:
    run = await session.get(ScanRun, payload.scan_run_id)
    if run is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Scan run not found")
    if run.status in _FINALIZED:
        raise HTTPException(status.HTTP_409_CONFLICT, "Scan run already finalized")

    # Bind ingest to the calling agent so a token cannot write results to a run
    # it has no business with: a run already claimed via poll may be reported
    # only by the agent that claimed it, and an agent may only write to runs in
    # its own segment (the same routing rule used to dispatch jobs). This closes
    # the gap where any enrolled token could inject observations into any run.
    if run.agent_id is not None and run.agent_id != str(agent.id):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Scan run was claimed by a different agent"
        )
    if run.scan_profile_id is not None:
        profile = await session.get(ScanProfile, run.scan_profile_id)
        if profile is not None and profile.segment != agent.segment:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN, "Scan run belongs to a different segment"
            )

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

    # Auto-discovery: a scanned host with open ports that isn't a known asset
    # becomes a low-criticality asset (with its hostname if reported), so the
    # inventory reflects what scans actually find.
    discovered = 0
    discovered_hosts: list[SourceAsset] = []
    for host in payload.hosts:
        if host.ip not in asset_map and host.ports:
            asset = Asset(
                ip=host.ip,
                hostname=host.hostname,
                criticality=Criticality.low,
                discovered=True,
            )
            session.add(asset)
            await session.flush()
            asset_map[host.ip] = asset.id
            discovered += 1
            discovered_hosts.append(SourceAsset(ip=host.ip, hostname=host.hostname))

    count = 0
    # Observations whose deterministic fingerprint is weak but carry a banner;
    # candidates for AI enrichment before change detection runs.
    enrich_candidates: list[tuple[Observation, str]] = []
    for host in payload.hosts:
        for port in host.ports:
            banner_hash = port.banner_sha256
            if banner_hash is None and port.banner is not None:
                banner_hash = hashlib.sha256(port.banner.encode("utf-8")).hexdigest()

            service = port.service
            version = port.version
            product = port.product
            confidence = port.fingerprint_confidence
            low_confidence = confidence is None or confidence < CONFIDENCE_FLOOR
            # Provenance: a confident edge fingerprint is the agent's nmap probe.
            fp_source = "agent" if service and not low_confidence else None

            # Deterministic server-side banner heuristic: resolve common
            # self-announcing banners (SSH/SMTP/FTP/IMAP/POP3/HTTP) with no LLM
            # cost, before the AI fallback runs.
            if low_confidence and port.banner:
                match = match_banner(port.banner)
                if match is not None:
                    service = match.service
                    product = match.product or product
                    version = match.version or version
                    confidence = match.confidence
                    fp_source = "heuristic"
                    low_confidence = False

            obs = Observation(
                ts=received_at,
                scan_run_id=run.id,
                asset_id=asset_map.get(host.ip),
                ip=host.ip,
                port=port.port,
                protocol=port.protocol,
                state=port.state,
                service=service,
                version=version,
                product=product,
                banner_sha256=banner_hash,
                fingerprint_confidence=confidence,
                fingerprint_source=fp_source,
            )
            session.add(obs)
            count += 1
            if port.banner and low_confidence:
                enrich_candidates.append((obs, port.banner))

    # AI assist (best-effort): refine weak fingerprints if a provider is set up.
    if ai_provider.name != "none" and enrich_candidates:
        await _enrich_observations(ai_provider, enrich_candidates[:_MAX_ENRICH])

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
            "discovered_assets": discovered,
        },
    )
    await session.commit()

    eff = await effective_settings(session)

    # Best-effort notification across every configured channel (email + chat
    # webhooks). A profile can opt out of notifications while still recording
    # its changes. notify_changes is best-effort per channel; this guard only
    # covers an unexpected failure building the channel list.
    if change_summaries:
        notify_ok = True
        if run.scan_profile_id is not None:
            prof = await session.get(ScanProfile, run.scan_profile_id)
            notify_ok = prof is None or prof.notify_enabled
        if notify_ok:
            try:
                await notify_changes(
                    change_summaries, eff, scan_profile_id=str(run.scan_profile_id)
                    if run.scan_profile_id is not None
                    else None,
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("change notification failed: %s", exc)

    # Best-effort NetBox writeback of just-discovered hosts, when enabled. The
    # manual push button stays the primary path; this is the opt-in automatic one.
    if discovered_hosts and source.name != "none" and eff.netbox_writeback_enabled:
        try:
            await source.push_assets(discovered_hosts)
        except Exception as exc:  # noqa: BLE001 - never fail ingest on writeback
            logger.warning("NetBox writeback failed: %s", exc)

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
        "discovered_assets": discovered,
    }
