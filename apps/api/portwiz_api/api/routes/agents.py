"""Scan agent enrollment and management.

Admins enroll agents (the plaintext token is returned once). Agents use that
token to authenticate to the ingest endpoint and to heartbeat.
"""

from __future__ import annotations

import datetime as dt
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.audit import append_audit
from ...core.db import get_session
from ...core.security import generate_agent_token, hash_agent_token
from ...models.agent import Agent
from ...models.user import User, UserRole
from ...schemas.agent import AgentCreate, AgentCreated, AgentRead
from ..deps import get_current_agent, require_roles

router = APIRouter(prefix="/agents", tags=["agents"])


def _utcnow() -> dt.datetime:
    return dt.datetime.now(tz=dt.timezone.utc)


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
    agent = Agent(name=payload.name, token_hash=hash_agent_token(token))
    session.add(agent)
    await session.flush()
    await append_audit(
        session,
        action="agent.enrolled",
        actor_id=current_user.id,
        actor_email=current_user.email,
        target_type="agent",
        target_id=str(agent.id),
        payload={"name": agent.name},
    )
    await session.commit()
    await session.refresh(agent)
    # The token is shown only here; only its hash is stored.
    return AgentCreated(id=agent.id, name=agent.name, token=token, created_at=agent.created_at)


@router.get("", response_model=list[AgentRead])
async def list_agents(
    _: User = Depends(require_roles(UserRole.admin, UserRole.auditor)),
    session: AsyncSession = Depends(get_session),
) -> list[Agent]:
    result = await session.execute(select(Agent).order_by(Agent.name))
    return list(result.scalars().all())


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
    agent: Agent = Depends(get_current_agent),
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    agent.last_seen_at = _utcnow()
    await session.commit()
    return {"status": "ok", "agent_id": str(agent.id)}
