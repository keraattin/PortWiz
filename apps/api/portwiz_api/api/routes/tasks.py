"""Tasks: follow-up work for confirmed changes (and manual items).

Reads are available to any authenticated user; writes require admin or
operator. Tasks are also created automatically by change detection.
"""

from __future__ import annotations

import datetime as dt
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.audit import append_audit
from ...core.db import get_session
from ...core.issue_tracker import (
    IssueTracker,
    build_task_issue,
    get_issue_tracker,
    map_jira_status,
)
from ...models.change import ChangeEvent
from ...models.task import Task
from ...models.user import User, UserRole
from ...schemas.task import TaskCreate, TaskRead, TaskUpdate
from ..deps import get_current_user, require_roles

router = APIRouter(prefix="/tasks", tags=["tasks"])

WriteDep = require_roles(UserRole.admin, UserRole.operator)


def _utcnow() -> dt.datetime:
    return dt.datetime.now(tz=dt.timezone.utc)


async def _validate_refs(
    session: AsyncSession,
    assignee_id: uuid.UUID | None,
    change_event_id: uuid.UUID | None,
) -> None:
    if assignee_id is not None and await session.get(User, assignee_id) is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Assignee does not exist")
    if change_event_id is not None and await session.get(ChangeEvent, change_event_id) is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Change event does not exist")


@router.get("", response_model=list[TaskRead])
async def list_tasks(
    task_status: str | None = None,
    assignee_id: uuid.UUID | None = None,
    change_event_id: uuid.UUID | None = None,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[Task]:
    query = select(Task).order_by(Task.created_at.desc())
    if task_status is not None:
        query = query.where(Task.status == task_status)
    if assignee_id is not None:
        query = query.where(Task.assignee_id == assignee_id)
    if change_event_id is not None:
        query = query.where(Task.change_event_id == change_event_id)
    result = await session.execute(query)
    return list(result.scalars().all())


@router.get("/{task_id}", response_model=TaskRead)
async def get_task(
    task_id: uuid.UUID,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Task:
    task = await session.get(Task, task_id)
    if task is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Task not found")
    return task


@router.post("", response_model=TaskRead, status_code=status.HTTP_201_CREATED)
async def create_task(
    payload: TaskCreate,
    current_user: User = Depends(WriteDep),
    session: AsyncSession = Depends(get_session),
) -> Task:
    await _validate_refs(session, payload.assignee_id, payload.change_event_id)
    task = Task(**payload.model_dump(), created_by=current_user.id)
    session.add(task)
    await session.flush()
    await append_audit(
        session,
        action="task.created",
        actor_id=current_user.id,
        actor_email=current_user.email,
        target_type="task",
        target_id=str(task.id),
        payload={"title": task.title},
    )
    await session.commit()
    await session.refresh(task)
    return task


@router.patch("/{task_id}", response_model=TaskRead)
async def update_task(
    task_id: uuid.UUID,
    payload: TaskUpdate,
    current_user: User = Depends(WriteDep),
    session: AsyncSession = Depends(get_session),
) -> Task:
    task = await session.get(Task, task_id)
    if task is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Task not found")
    changes = payload.model_dump(exclude_unset=True)
    if "assignee_id" in changes:
        await _validate_refs(session, changes["assignee_id"], None)
    for key, value in changes.items():
        setattr(task, key, value)
    task.updated_at = _utcnow()
    await append_audit(
        session,
        action="task.updated",
        actor_id=current_user.id,
        actor_email=current_user.email,
        target_type="task",
        target_id=str(task.id),
        payload={"changes": list(changes.keys())},
    )
    await session.commit()
    await session.refresh(task)
    return task


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(
    task_id: uuid.UUID,
    current_user: User = Depends(WriteDep),
    session: AsyncSession = Depends(get_session),
) -> None:
    task = await session.get(Task, task_id)
    if task is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Task not found")
    await session.delete(task)
    await append_audit(
        session,
        action="task.deleted",
        actor_id=current_user.id,
        actor_email=current_user.email,
        target_type="task",
        target_id=str(task_id),
    )
    await session.commit()


@router.post("/{task_id}/jira", response_model=TaskRead)
async def link_task_to_jira(
    task_id: uuid.UUID,
    current_user: User = Depends(WriteDep),
    session: AsyncSession = Depends(get_session),
    tracker: IssueTracker = Depends(get_issue_tracker),
) -> Task:
    task = await session.get(Task, task_id)
    if task is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Task not found")
    if task.jira_key:
        raise HTTPException(status.HTTP_409_CONFLICT, "Task already linked to Jira")

    summary, description = build_task_issue(task)
    # Carry the linked change's severity so priority mapping can apply.
    severity = None
    if task.change_event_id:
        change = await session.get(ChangeEvent, task.change_event_id)
        severity = change.severity if change else None
    key = await tracker.create_issue(summary, description, severity=severity)
    if not key:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Issue tracker is not configured")

    task.jira_key = key
    task.updated_at = _utcnow()
    await append_audit(
        session,
        action="task.jira_linked",
        actor_id=current_user.id,
        actor_email=current_user.email,
        target_type="task",
        target_id=str(task.id),
        payload={"jira_key": key},
    )
    await session.commit()
    await session.refresh(task)
    return task


@router.post("/{task_id}/jira/sync", response_model=TaskRead)
async def sync_task_from_jira(
    task_id: uuid.UUID,
    current_user: User = Depends(WriteDep),
    session: AsyncSession = Depends(get_session),
    tracker: IssueTracker = Depends(get_issue_tracker),
) -> Task:
    task = await session.get(Task, task_id)
    if task is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Task not found")
    if not task.jira_key:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Task is not linked to Jira")

    jira_status = await tracker.get_status(task.jira_key)
    mapped = map_jira_status(jira_status)
    if mapped is not None:
        task.status = mapped
        task.updated_at = _utcnow()
    await append_audit(
        session,
        action="task.jira_synced",
        actor_id=current_user.id,
        actor_email=current_user.email,
        target_type="task",
        target_id=str(task.id),
        payload={"jira_status": jira_status, "mapped": mapped},
    )
    await session.commit()
    await session.refresh(task)
    return task
