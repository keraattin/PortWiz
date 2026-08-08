"""Scan profiles, manual triggering, and scan-run history.

Reads are available to any authenticated user; writes (and triggering a scan)
require admin or operator.
"""

from __future__ import annotations

import datetime as dt
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.app_settings import effective_settings
from ...core.audit import append_audit
from ...core.db import get_session
from ...core.issue_tracker import (
    IssueTracker,
    NullTracker,
    export_changes_to_tracker,
    get_issue_tracker,
)
from ...models.change import ChangeEvent
from ...models.scan import (
    Observation,
    ScanProfile,
    ScanRun,
    ScanRunStatus,
    ScanSource,
    ScanType,
)
from ...models.user import User, UserRole
from ...schemas.scan import (
    ObservationRead,
    ScanProfileCreate,
    ScanProfileRead,
    ScanProfileUpdate,
    ScanRunJiraExport,
    ScanRunRead,
)
from ..deps import get_current_user, require_roles

WriteDep = require_roles(UserRole.admin, UserRole.operator)

profiles_router = APIRouter(prefix="/scan-profiles", tags=["scans"])
runs_router = APIRouter(prefix="/scan-runs", tags=["scans"])


def _utcnow() -> dt.datetime:
    return dt.datetime.now(tz=dt.timezone.utc)


@profiles_router.get("", response_model=list[ScanProfileRead])
async def list_profiles(
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[ScanProfile]:
    result = await session.execute(select(ScanProfile).order_by(ScanProfile.name))
    return list(result.scalars().all())


@profiles_router.post("", response_model=ScanProfileRead, status_code=status.HTTP_201_CREATED)
async def create_profile(
    payload: ScanProfileCreate,
    current_user: User = Depends(WriteDep),
    session: AsyncSession = Depends(get_session),
) -> ScanProfile:
    # Fields the request omits fall back to the admin-configured scan defaults.
    data = payload.model_dump()
    explicit = payload.model_dump(exclude_unset=True)
    eff = await effective_settings(session)
    if "ports" not in explicit:
        data["ports"] = eff.default_scan_ports
    if "scan_type" not in explicit:
        data["scan_type"] = ScanType(eff.default_scan_type)
    if "service_detection" not in explicit:
        data["service_detection"] = eff.default_service_detection
    if "rate_limit_pps" not in explicit:
        data["rate_limit_pps"] = eff.default_scan_rate_limit_pps

    profile = ScanProfile(**data, created_by=current_user.id)
    session.add(profile)
    await session.flush()
    await append_audit(
        session,
        action="scan_profile.created",
        actor_id=current_user.id,
        actor_email=current_user.email,
        target_type="scan_profile",
        target_id=str(profile.id),
        payload={"name": profile.name, "targets": profile.targets},
    )
    await session.commit()
    await session.refresh(profile)
    return profile


@profiles_router.patch("/{profile_id}", response_model=ScanProfileRead)
async def update_profile(
    profile_id: uuid.UUID,
    payload: ScanProfileUpdate,
    current_user: User = Depends(WriteDep),
    session: AsyncSession = Depends(get_session),
) -> ScanProfile:
    profile = await session.get(ScanProfile, profile_id)
    if profile is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Scan profile not found")
    changes = payload.model_dump(exclude_unset=True)
    for key, value in changes.items():
        setattr(profile, key, value)
    profile.updated_at = _utcnow()
    await append_audit(
        session,
        action="scan_profile.updated",
        actor_id=current_user.id,
        actor_email=current_user.email,
        target_type="scan_profile",
        target_id=str(profile.id),
        payload={"changes": list(changes.keys())},
    )
    await session.commit()
    await session.refresh(profile)
    return profile


@profiles_router.delete("/{profile_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_profile(
    profile_id: uuid.UUID,
    current_user: User = Depends(WriteDep),
    session: AsyncSession = Depends(get_session),
) -> None:
    profile = await session.get(ScanProfile, profile_id)
    if profile is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Scan profile not found")
    await session.delete(profile)
    await append_audit(
        session,
        action="scan_profile.deleted",
        actor_id=current_user.id,
        actor_email=current_user.email,
        target_type="scan_profile",
        target_id=str(profile_id),
    )
    await session.commit()


@profiles_router.post(
    "/{profile_id}/run", response_model=ScanRunRead, status_code=status.HTTP_201_CREATED
)
async def trigger_run(
    profile_id: uuid.UUID,
    current_user: User = Depends(WriteDep),
    session: AsyncSession = Depends(get_session),
) -> ScanRun:
    profile = await session.get(ScanProfile, profile_id)
    if profile is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Scan profile not found")

    run = ScanRun(
        scan_profile_id=profile.id,
        scan_source=ScanSource(profile.scan_source),
        status=ScanRunStatus.pending,
    )
    session.add(run)
    await session.flush()
    await append_audit(
        session,
        action="scan_run.triggered",
        actor_id=current_user.id,
        actor_email=current_user.email,
        target_type="scan_run",
        target_id=str(run.id),
        payload={"scan_profile_id": str(profile.id)},
    )
    await session.commit()
    await session.refresh(run)
    return run


@runs_router.get("", response_model=list[ScanRunRead])
async def list_runs(
    scan_profile_id: uuid.UUID | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[ScanRun]:
    query = select(ScanRun).order_by(ScanRun.created_at.desc()).limit(limit)
    if scan_profile_id is not None:
        query = query.where(ScanRun.scan_profile_id == scan_profile_id)
    result = await session.execute(query)
    return list(result.scalars().all())


@runs_router.get("/{run_id}", response_model=ScanRunRead)
async def get_run(
    run_id: uuid.UUID,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ScanRun:
    run = await session.get(ScanRun, run_id)
    if run is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Scan run not found")
    return run


@runs_router.delete("/{run_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_run(
    run_id: uuid.UUID,
    current_user: User = Depends(WriteDep),
    session: AsyncSession = Depends(get_session),
) -> None:
    """Delete a scan run and its observations (the raw results). Confirmed change
    events are kept but detached from the run, so change history stays intact."""
    run = await session.get(ScanRun, run_id)
    if run is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Scan run not found")
    run_status = getattr(run.status, "value", run.status)
    obs_count = (
        await session.execute(
            select(func.count())
            .select_from(Observation)
            .where(Observation.scan_run_id == run_id)
        )
    ).scalar_one()
    # Detach change events (preserve the compliance record), then drop the raw
    # observations and the run itself.
    await session.execute(
        update(ChangeEvent)
        .where(ChangeEvent.scan_run_id == run_id)
        .values(scan_run_id=None)
    )
    await session.execute(delete(Observation).where(Observation.scan_run_id == run_id))
    await session.delete(run)
    await append_audit(
        session,
        action="scan_run.deleted",
        actor_id=current_user.id,
        actor_email=current_user.email,
        target_type="scan_run",
        target_id=str(run_id),
        payload={"observations_deleted": int(obs_count), "status": run_status},
    )
    await session.commit()


@runs_router.get("/{run_id}/observations", response_model=list[ObservationRead])
async def list_run_observations(
    run_id: uuid.UUID,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[Observation]:
    result = await session.execute(
        select(Observation)
        .where(Observation.scan_run_id == run_id)
        .order_by(Observation.ip, Observation.port)
    )
    return list(result.scalars().all())


@runs_router.post("/{run_id}/jira", response_model=ScanRunJiraExport)
async def export_run_to_jira(
    run_id: uuid.UUID,
    current_user: User = Depends(WriteDep),
    session: AsyncSession = Depends(get_session),
    tracker: IssueTracker = Depends(get_issue_tracker),
) -> ScanRunJiraExport:
    """Create Jira issues for this run's open confirmed changes.

    Changes already linked to Jira are skipped so a re-export never duplicates
    issues. Requires Jira to be configured, otherwise 400.
    """
    run = await session.get(ScanRun, run_id)
    if run is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Scan run not found")
    if isinstance(tracker, NullTracker):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Issue tracker is not configured"
        )

    changes = list(
        (
            await session.execute(
                select(ChangeEvent).where(
                    ChangeEvent.scan_run_id == run_id,
                    ChangeEvent.status == "open",
                )
            )
        ).scalars().all()
    )
    result = await export_changes_to_tracker(session, changes, tracker)
    await append_audit(
        session,
        action="scan_run.jira_exported",
        actor_id=current_user.id,
        actor_email=current_user.email,
        target_type="scan_run",
        target_id=str(run_id),
        payload=dict(result),
    )
    await session.commit()
    return ScanRunJiraExport(**result)
