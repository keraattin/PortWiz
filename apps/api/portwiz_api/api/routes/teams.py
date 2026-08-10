"""Teams and their membership.

A team is a named group of users; assets and VLANs can be assigned to one via
``owner_team_id``. Managing teams (create/update/delete, add/remove members) is
admin-only; listing and viewing are open to any authenticated user so the
owner-team pickers on the inventory forms work. No access control is derived
from team membership yet.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.audit import append_audit
from ...core.db import get_session
from ...models.asset import VLAN, Asset
from ...models.team import Team, TeamMember
from ...models.user import User, UserRole
from ...schemas.team import (
    TeamCreate,
    TeamDetail,
    TeamMemberAdd,
    TeamMemberRead,
    TeamRead,
    TeamUpdate,
)
from ..deps import get_current_user, require_roles

router = APIRouter(prefix="/teams", tags=["teams"])

AdminDep = require_roles(UserRole.admin)


async def _member_counts(session: AsyncSession) -> dict[uuid.UUID, int]:
    rows = (
        await session.execute(
            select(TeamMember.team_id, func.count()).group_by(TeamMember.team_id)
        )
    ).all()
    return {team_id: int(n) for team_id, n in rows}


async def _members(session: AsyncSession, team_id: uuid.UUID) -> list[TeamMemberRead]:
    rows = (
        await session.execute(
            select(User.id, User.email, User.full_name)
            .join(TeamMember, TeamMember.user_id == User.id)
            .where(TeamMember.team_id == team_id)
            .order_by(User.email)
        )
    ).all()
    return [
        TeamMemberRead(user_id=uid, email=email, full_name=full_name)
        for uid, email, full_name in rows
    ]


def _read(team: Team, member_count: int) -> TeamRead:
    return TeamRead(
        id=team.id,
        name=team.name,
        description=team.description,
        created_at=team.created_at,
        member_count=member_count,
    )


@router.get("", response_model=list[TeamRead])
async def list_teams(
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[TeamRead]:
    teams = (await session.execute(select(Team).order_by(Team.name))).scalars().all()
    counts = await _member_counts(session)
    return [_read(t, counts.get(t.id, 0)) for t in teams]


@router.post("", response_model=TeamRead, status_code=status.HTTP_201_CREATED)
async def create_team(
    payload: TeamCreate,
    current_user: User = Depends(AdminDep),
    session: AsyncSession = Depends(get_session),
) -> TeamRead:
    existing = (
        await session.execute(select(Team).where(Team.name == payload.name))
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Team name already exists")
    team = Team(name=payload.name, description=payload.description)
    session.add(team)
    await session.flush()
    await append_audit(
        session,
        action="team.created",
        actor_id=current_user.id,
        actor_email=current_user.email,
        target_type="team",
        target_id=str(team.id),
        payload={"name": team.name},
    )
    await session.commit()
    await session.refresh(team)
    return _read(team, 0)


@router.get("/{team_id}", response_model=TeamDetail)
async def get_team(
    team_id: uuid.UUID,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> TeamDetail:
    team = await session.get(Team, team_id)
    if team is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Team not found")
    members = await _members(session, team_id)
    return TeamDetail(
        id=team.id,
        name=team.name,
        description=team.description,
        created_at=team.created_at,
        member_count=len(members),
        members=members,
    )


@router.patch("/{team_id}", response_model=TeamRead)
async def update_team(
    team_id: uuid.UUID,
    payload: TeamUpdate,
    current_user: User = Depends(AdminDep),
    session: AsyncSession = Depends(get_session),
) -> TeamRead:
    team = await session.get(Team, team_id)
    if team is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Team not found")
    changes = payload.model_dump(exclude_unset=True)
    if "name" in changes and changes["name"] != team.name:
        dup = (
            await session.execute(select(Team).where(Team.name == changes["name"]))
        ).scalar_one_or_none()
        if dup is not None:
            raise HTTPException(status.HTTP_409_CONFLICT, "Team name already exists")
    for key, value in changes.items():
        setattr(team, key, value)
    await append_audit(
        session,
        action="team.updated",
        actor_id=current_user.id,
        actor_email=current_user.email,
        target_type="team",
        target_id=str(team.id),
        payload={"name": team.name},
    )
    await session.commit()
    await session.refresh(team)
    counts = await _member_counts(session)
    return _read(team, counts.get(team.id, 0))


@router.delete("/{team_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_team(
    team_id: uuid.UUID,
    current_user: User = Depends(AdminDep),
    session: AsyncSession = Depends(get_session),
) -> None:
    team = await session.get(Team, team_id)
    if team is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Team not found")
    name = team.name
    # Detach the team from assets/VLANs and drop its memberships first.
    await session.execute(
        update(Asset).where(Asset.owner_team_id == team_id).values(owner_team_id=None)
    )
    await session.execute(
        update(VLAN).where(VLAN.owner_team_id == team_id).values(owner_team_id=None)
    )
    await session.execute(delete(TeamMember).where(TeamMember.team_id == team_id))
    await session.delete(team)
    await append_audit(
        session,
        action="team.deleted",
        actor_id=current_user.id,
        actor_email=current_user.email,
        target_type="team",
        target_id=str(team_id),
        payload={"name": name},
    )
    await session.commit()


@router.post(
    "/{team_id}/members",
    response_model=TeamMemberRead,
    status_code=status.HTTP_201_CREATED,
)
async def add_member(
    team_id: uuid.UUID,
    payload: TeamMemberAdd,
    current_user: User = Depends(AdminDep),
    session: AsyncSession = Depends(get_session),
) -> TeamMemberRead:
    if await session.get(Team, team_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Team not found")
    user = await session.get(User, payload.user_id)
    if user is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Referenced user does not exist")
    existing = (
        await session.execute(
            select(TeamMember).where(
                TeamMember.team_id == team_id,
                TeamMember.user_id == payload.user_id,
            )
        )
    ).scalar_one_or_none()
    if existing is None:  # idempotent add
        session.add(TeamMember(team_id=team_id, user_id=payload.user_id))
        await append_audit(
            session,
            action="team.member_added",
            actor_id=current_user.id,
            actor_email=current_user.email,
            target_type="team",
            target_id=str(team_id),
            payload={"user": user.email},
        )
        await session.commit()
    return TeamMemberRead(user_id=user.id, email=user.email, full_name=user.full_name)


@router.delete(
    "/{team_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def remove_member(
    team_id: uuid.UUID,
    user_id: uuid.UUID,
    current_user: User = Depends(AdminDep),
    session: AsyncSession = Depends(get_session),
) -> None:
    row = (
        await session.execute(
            select(TeamMember).where(
                TeamMember.team_id == team_id, TeamMember.user_id == user_id
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Membership not found")
    await session.delete(row)
    await append_audit(
        session,
        action="team.member_removed",
        actor_id=current_user.id,
        actor_email=current_user.email,
        target_type="team",
        target_id=str(team_id),
        payload={"user_id": str(user_id)},
    )
    await session.commit()
