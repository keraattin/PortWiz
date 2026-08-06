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
from ..models.change import ChangeEvent, PortState, PortSuppression
from ..models.scan import Observation, ScanRun, ScanRunStatus
from ..models.task import Task, TaskStatus

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

    from .app_settings import effective_settings

    # Admin-tunable: how many consecutive runs a state must persist to confirm.
    confirmations = max(1, (await effective_settings(session)).change_confirmations)
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

    # Known ports: once a team acknowledges a change on a port, later identical
    # changes (same ip/port/protocol/type) are recorded but auto-acknowledged and
    # not re-alarmed, so a flapping-but-known port does not page the team on every
    # transition. Resolved is deliberately excluded: a resolved change recurring
    # is a regression worth surfacing again.
    ack_rows = (
        await session.execute(
            select(
                ChangeEvent.ip,
                ChangeEvent.port,
                ChangeEvent.protocol,
                ChangeEvent.change_type,
            ).where(
                ChangeEvent.scan_profile_id == run.scan_profile_id,
                ChangeEvent.status == "acknowledged",
            )
        )
    ).all()
    known_ports = {(ip, port, proto, ctype) for ip, port, proto, ctype in ack_rows}

    # Ports marked as false positives are absorbed silently: their state still
    # tracks (so the machine stays consistent) but they never raise a change,
    # open a task, or notify. Global across profiles, matching the ports view.
    supp_rows = (
        await session.execute(
            select(
                PortSuppression.ip, PortSuppression.port, PortSuppression.protocol
            )
        )
    ).all()
    suppressed = {(ip, port, proto) for ip, port, proto in supp_rows}

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

        if state.candidate_count >= confirmations:
            # A false-positive port confirms into its new state silently: no
            # event, no task, no notification.
            if key not in suppressed:
                # A recurrence on a known port is recorded but pre-acknowledged and
                # marked processed, so it never re-alarms or reopens a task.
                known = (ip, port, protocol, change_type) in known_ports
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
                    status="acknowledged" if known else "open",
                    notified_at=now if known else None,
                    detected_at=now,
                )
                session.add(event)
                events.append(event)

                # Open a follow-up task only for changes that still need triage.
                if not known:
                    session.add(
                        Task(
                            title=f"Review {change_type} on {ip}:{port}/{protocol}",
                            description=(
                                f"Confirmed {change_type} change on {ip}:{port}/{protocol} "
                                f"(severity {_SEVERITY.get(change_type, 'medium')})."
                            ),
                            status=TaskStatus.open,
                            change_event_id=event.id,
                        )
                    )

            state.confirmed_state = desired.state
            state.confirmed_service = desired.service
            state.confirmed_version = desired.version
            if desired.state == "open":
                state.last_seen_open_at = now
            _clear_candidate(state)

    return events
