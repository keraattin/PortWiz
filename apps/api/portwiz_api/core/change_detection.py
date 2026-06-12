"""Flapping-aware change detection.

After a scan run completes, this compares the observed open ports against the
confirmed per-port state and only raises a ChangeEvent once a difference has
persisted for ``CONFIRMATIONS`` consecutive runs. That filters out network
jitter (a port briefly missing or flapping), which is the difference between a
noisy port scanner and audit-grade change evidence.

Scope/closes: a previously confirmed-open port that is absent from a completed
run is treated as a candidate "closed". This assumes a profile keeps scanning
the same targets/ports between runs (true for the MVP); changing a profile's
scope can produce spurious closes, which Phase 2 hardens.
"""

from __future__ import annotations

import datetime as dt
import uuid
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.asset import Asset
from ..models.change import ChangeEvent, PortState
from ..models.scan import Observation, ScanRun, ScanRunStatus

# Consecutive runs a new state must persist before it is confirmed.
CONFIRMATIONS = 2

_SEVERITY = {
    "opened": "high",
    "closed": "medium",
    "service_changed": "medium",
    "version_changed": "low",
}


def _utcnow() -> dt.datetime:
    return dt.datetime.now(tz=dt.timezone.utc)


@dataclass(frozen=True)
class Desired:
    state: str  # "open" | "closed"
    service: str | None
    version: str | None


def _change_type(state: PortState, desired: Desired) -> str | None:
    """Return the change type if confirmed != desired, else None."""
    if state.confirmed_state != desired.state:
        return "opened" if desired.state == "open" else "closed"
    if desired.state == "open":
        if (state.confirmed_service or "") != (desired.service or ""):
            return "service_changed"
        if (state.confirmed_version or "") != (desired.version or ""):
            return "version_changed"
    return None


def _same_candidate(state: PortState, desired: Desired) -> bool:
    return (
        state.candidate_state == desired.state
        and (state.candidate_service or "") == (desired.service or "")
        and (state.candidate_version or "") == (desired.version or "")
    )


def _clear_candidate(state: PortState) -> None:
    state.candidate_state = None
    state.candidate_service = None
    state.candidate_version = None
    state.candidate_count = 0


async def detect_changes(session: AsyncSession, run: ScanRun) -> list[ChangeEvent]:
    """Update port states for ``run``'s profile and return confirmed changes.

    Only runs detection for completed runs that belong to a scan profile. The
    caller commits the surrounding transaction.
    """
    if run.scan_profile_id is None or run.status != ScanRunStatus.completed:
        return []

    now = _utcnow()

    observations = (
        await session.execute(
            select(Observation).where(
                Observation.scan_run_id == run.id, Observation.state == "open"
            )
        )
    ).scalars().all()
    observed: dict[tuple[str, int, str], Desired] = {
        (o.ip, o.port, o.protocol): Desired("open", o.service, o.version)
        for o in observations
    }

    asset_map: dict[str, uuid.UUID] = {}
    ips = {ip for ip, _, _ in observed}
    if ips:
        rows = (
            await session.execute(select(Asset.id, Asset.ip).where(Asset.ip.in_(ips)))
        ).all()
        asset_map = {ip: asset_id for asset_id, ip in rows}

    states = (
        await session.execute(
            select(PortState).where(PortState.scan_profile_id == run.scan_profile_id)
        )
    ).scalars().all()
    state_by_key = {(s.ip, s.port, s.protocol): s for s in states}

    prior_completed = (
        await session.execute(
            select(func.count())
            .select_from(ScanRun)
            .where(
                ScanRun.scan_profile_id == run.scan_profile_id,
                ScanRun.status == ScanRunStatus.completed,
                ScanRun.id != run.id,
            )
        )
    ).scalar_one()
    baseline = prior_completed == 0

    # The comparison universe: everything observed now, plus every port that is
    # currently confirmed-open (so a disappearance can be detected as a close).
    universe: set[tuple[str, int, str]] = set(observed)
    for key, state in state_by_key.items():
        if state.confirmed_state == "open":
            universe.add(key)

    events: list[ChangeEvent] = []

    for key in universe:
        ip, port, protocol = key
        desired = observed.get(key, Desired("closed", None, None))
        state = state_by_key.get(key)

        if state is None:
            if baseline:
                if desired.state == "open":
                    session.add(
                        PortState(
                            scan_profile_id=run.scan_profile_id,
                            ip=ip,
                            port=port,
                            protocol=protocol,
                            confirmed_state="open",
                            confirmed_service=desired.service,
                            confirmed_version=desired.version,
                            last_seen_open_at=now,
                            updated_at=now,
                        )
                    )
                continue
            # New port outside baseline: start from a confirmed-closed baseline.
            state = PortState(
                scan_profile_id=run.scan_profile_id,
                ip=ip,
                port=port,
                protocol=protocol,
                confirmed_state="closed",
                updated_at=now,
            )
            session.add(state)
            state_by_key[key] = state

        if baseline:
            # Establish baseline without raising events.
            state.confirmed_state = desired.state
            state.confirmed_service = desired.service
            state.confirmed_version = desired.version
            if desired.state == "open":
                state.last_seen_open_at = now
            _clear_candidate(state)
            state.updated_at = now
            continue

        change_type = _change_type(state, desired)
        if change_type is None:
            _clear_candidate(state)
            if desired.state == "open":
                state.last_seen_open_at = now
            state.updated_at = now
            continue

        if _same_candidate(state, desired):
            state.candidate_count += 1
        else:
            state.candidate_state = desired.state
            state.candidate_service = desired.service
            state.candidate_version = desired.version
            state.candidate_count = 1
        state.updated_at = now

        if state.candidate_count >= CONFIRMATIONS:
            event = ChangeEvent(
                scan_profile_id=run.scan_profile_id,
                scan_run_id=run.id,
                asset_id=asset_map.get(ip),
                ip=ip,
                port=port,
                protocol=protocol,
                change_type=change_type,
                before={
                    "state": state.confirmed_state,
                    "service": state.confirmed_service,
                    "version": state.confirmed_version,
                },
                after={
                    "state": desired.state,
                    "service": desired.service,
                    "version": desired.version,
                },
                severity=_SEVERITY.get(change_type, "medium"),
                status="open",
                detected_at=now,
            )
            session.add(event)
            events.append(event)

            state.confirmed_state = desired.state
            state.confirmed_service = desired.service
            state.confirmed_version = desired.version
            if desired.state == "open":
                state.last_seen_open_at = now
            _clear_candidate(state)

    return events
