"""Scan agent enrollment and management.

Admins enroll agents (the plaintext token is returned once). Agents use that
token to authenticate to the ingest endpoint and to heartbeat.
"""

from __future__ import annotations

import datetime as dt
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.app_settings import effective_settings
from ...core.audit import append_audit
from ...core.db import get_session
from ...core.security import generate_agent_token, hash_agent_token
from ...models.agent import Agent
from ...models.scan import ScanProfile, ScanRun, ScanRunStatus, ScanSource, ScanType
from ...models.user import User, UserRole
from ...schemas.agent import (
    AgentConfig,
    AgentCreate,
    AgentCreated,
    AgentHeartbeat,
    AgentRead,
    AgentTokenRotated,
    AgentUpdate,
)
from ...schemas.scan import ScanJobOut
from ..deps import get_current_agent, require_roles

router = APIRouter(prefix="/agents", tags=["agents"])


def _utcnow() -> dt.datetime:
    return dt.datetime.now(tz=dt.timezone.utc)


def _client_ip(request: Request) -> str | None:
    """The agent's source IP, honouring a reverse proxy's forwarded header.

    In production a single-origin nginx proxies agent traffic, so the real
    client address arrives in X-Forwarded-For (first hop). Fall back to the
    direct peer address for a direct connection.
    """
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip() or None
    return request.client.host if request.client else None


@router.post("", response_model=AgentCreated, status_code=status.HTTP_201_CREATED)
async def enroll_agent(
    payload: AgentCreate,
    current_user: User = Depends(require_roles(UserRole.admin)),
    session: AsyncSession = Depends(get_session),
) -> AgentCreated:
    existing = (
        await session.execute(select(Agent).where(Agent.name == payload.name))
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Agent name already exists")

    token = generate_agent_token()
    agent = Agent(
        name=payload.name, token_hash=hash_agent_token(token), segment=payload.segment
    )
    session.add(agent)
    await session.flush()
    await append_audit(
        session,
        action="agent.enrolled",
        actor_id=current_user.id,
        actor_email=current_user.email,
        target_type="agent",
        target_id=str(agent.id),
        payload={"name": agent.name, "segment": agent.segment},
    )
    await session.commit()
    await session.refresh(agent)
    # The token is shown only here; only its hash is stored.
    return AgentCreated(
        id=agent.id,
        name=agent.name,
        segment=agent.segment,
        token=token,
        created_at=agent.created_at,
    )


@router.get("", response_model=list[AgentRead])
async def list_agents(
    _: User = Depends(require_roles(UserRole.admin, UserRole.auditor)),
    session: AsyncSession = Depends(get_session),
) -> list[Agent]:
    result = await session.execute(select(Agent).order_by(Agent.name))
    return list(result.scalars().all())


@router.patch("/{agent_id}", response_model=AgentRead)
async def update_agent(
    agent_id: uuid.UUID,
    payload: AgentUpdate,
    current_user: User = Depends(require_roles(UserRole.admin)),
    session: AsyncSession = Depends(get_session),
) -> Agent:
    agent = await session.get(Agent, agent_id)
    if agent is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Agent not found")
    changes = payload.model_dump(exclude_unset=True)
    for key, value in changes.items():
        setattr(agent, key, value)
    await append_audit(
        session,
        action="agent.updated",
        actor_id=current_user.id,
        actor_email=current_user.email,
        target_type="agent",
        target_id=str(agent.id),
        payload={"changes": list(changes.keys())},
    )
    await session.commit()
    await session.refresh(agent)
    return agent


@router.post("/{agent_id}/rotate-token", response_model=AgentTokenRotated)
async def rotate_agent_token(
    agent_id: uuid.UUID,
    current_user: User = Depends(require_roles(UserRole.admin)),
    session: AsyncSession = Depends(get_session),
) -> AgentTokenRotated:
    """Issue a fresh bearer token, invalidating the old one immediately.

    Use this if a token may be compromised, or to rotate credentials on a
    schedule. The agent must be redeployed with the new token; the previous
    token stops authenticating the moment this returns.
    """
    agent = await session.get(Agent, agent_id)
    if agent is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Agent not found")

    token = generate_agent_token()
    agent.token_hash = hash_agent_token(token)
    agent.token_rotated_at = _utcnow()
    await append_audit(
        session,
        action="agent.token_rotated",
        actor_id=current_user.id,
        actor_email=current_user.email,
        target_type="agent",
        target_id=str(agent.id),
        payload={"name": agent.name},
    )
    await session.commit()
    await session.refresh(agent)
    # The new token is shown only here; only its hash is stored.
    return AgentTokenRotated(
        id=agent.id,
        name=agent.name,
        token=token,
        token_rotated_at=agent.token_rotated_at,
    )


@router.delete("/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_agent(
    agent_id: uuid.UUID,
    current_user: User = Depends(require_roles(UserRole.admin)),
    session: AsyncSession = Depends(get_session),
) -> None:
    agent = await session.get(Agent, agent_id)
    if agent is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Agent not found")
    await session.delete(agent)
    await append_audit(
        session,
        action="agent.deleted",
        actor_id=current_user.id,
        actor_email=current_user.email,
        target_type="agent",
        target_id=str(agent_id),
    )
    await session.commit()


@router.post("/heartbeat")
async def heartbeat(
    request: Request,
    payload: AgentHeartbeat | None = None,
    agent: Agent = Depends(get_current_agent),
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    agent.last_seen_at = _utcnow()
    agent.last_ip = _client_ip(request)
    if payload is not None:
        # Only overwrite when the agent actually reports a value, so an older
        # agent that sends nothing keeps its last-known metadata.
        if payload.version is not None:
            agent.version = payload.version
        if payload.platform is not None:
            agent.platform = payload.platform
    await session.commit()
    return {"status": "ok", "agent_id": str(agent.id)}


@router.get("/me/config", response_model=AgentConfig)
async def my_config(
    agent: Agent = Depends(get_current_agent),
    session: AsyncSession = Depends(get_session),
) -> AgentConfig:
    """Effective config for the calling agent: the global poll interval unless
    this agent has an override. The agent fetches this to self-tune its cadence
    without a redeploy."""
    eff = await effective_settings(session)
    return AgentConfig(poll_seconds=agent.poll_seconds_override or eff.agent_poll_seconds)


@router.get("/jobs")
async def poll_job(
    agent: Agent = Depends(get_current_agent),
    session: AsyncSession = Depends(get_session),
):
    """Claim the oldest pending scan run for this agent's segment.

    Runs are routed by segment: an agent only claims runs whose scan profile has
    the same segment, and an agent with no segment claims unsegmented profiles.
    Returns 204 when there is no matching work. Note: for the MVP this claim is a
    simple select-then-update; multi-agent claim contention is hardened later.
    """
    segment_match = (
        ScanProfile.segment.is_(None)
        if agent.segment is None
        else ScanProfile.segment == agent.segment
    )
    run = (
        await session.execute(
            select(ScanRun)
            .join(ScanProfile, ScanRun.scan_profile_id == ScanProfile.id)
            .where(ScanRun.status == ScanRunStatus.pending)
            .where(segment_match)
            .order_by(ScanRun.created_at.asc())
            .limit(1)
            # Lock the claimed row and let concurrent agents skip it (PostgreSQL;
            # SQLite ignores row locking). Prevents two agents claiming one run.
            .with_for_update(skip_locked=True, of=ScanRun)
        )
    ).scalar_one_or_none()
    if run is None:
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    profile = await session.get(ScanProfile, run.scan_profile_id)
    if profile is None:
        run.status = ScanRunStatus.failed
        run.error = "scan profile no longer exists"
        await session.commit()
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    now = _utcnow()
    run.status = ScanRunStatus.running
    run.agent_id = str(agent.id)
    run.started_at = now
    run.attempts = run.attempts + 1
    agent.last_seen_at = now

    # A per-agent rate cap only ever lowers the profile's rate (fragile segment).
    rate_limit_pps = profile.rate_limit_pps
    if agent.rate_limit_pps_override:
        rate_limit_pps = min(rate_limit_pps, agent.rate_limit_pps_override)

    job = ScanJobOut(
        job_id=uuid.uuid4(),
        scan_run_id=run.id,
        scan_profile_id=profile.id,
        targets=list(profile.targets),
        ports=profile.ports,
        scan_type=ScanType(profile.scan_type),
        service_detection=profile.service_detection,
        rate_limit_pps=rate_limit_pps,
        scan_source=ScanSource(profile.scan_source),
    )
    await append_audit(
        session,
        action="scan_run.dispatched",
        actor_email=f"agent:{agent.name}",
        target_type="scan_run",
        target_id=str(run.id),
        payload={"agent": agent.name},
    )
    await session.commit()
    return job


# Declared last so the literal agent routes (/heartbeat, /jobs) win the match;
# a bare "/{agent_id}" earlier would capture "jobs" and reject it as a non-UUID.
@router.get("/{agent_id}", response_model=AgentRead)
async def get_agent(
    agent_id: uuid.UUID,
    _: User = Depends(require_roles(UserRole.admin, UserRole.auditor)),
    session: AsyncSession = Depends(get_session),
) -> Agent:
    agent = await session.get(Agent, agent_id)
    if agent is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Agent not found")
    return agent
