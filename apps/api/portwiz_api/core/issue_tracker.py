"""Issue tracker integration (Jira).

A provider-agnostic interface so other trackers (ServiceNow, GitHub Issues)
can be added later. ``get_issue_tracker`` is a FastAPI dependency, which also
makes it trivial to inject a fake in tests. Config is imported lazily.
"""

from __future__ import annotations

import logging
from typing import Any, Protocol

import httpx
from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.change import ChangeEvent
from ..models.task import Task
from .db import get_session

logger = logging.getLogger("portwiz.issue_tracker")


class IssueTracker(Protocol):
    async def create_issue(self, summary: str, description: str) -> str | None: ...
    async def get_status(self, key: str) -> str | None: ...
    async def verify(self) -> tuple[bool, str]: ...


class NullTracker:
    """Used when no tracker is configured. Every operation is a no-op."""

    async def create_issue(self, summary: str, description: str) -> str | None:
        return None

    async def get_status(self, key: str) -> str | None:
        return None

    async def verify(self) -> tuple[bool, str]:
        return False, "Jira is not configured."


def _adf(text: str) -> dict[str, Any]:
    """Minimal Atlassian Document Format wrapper for a plain-text description."""
    return {
        "type": "doc",
        "version": 1,
        "content": [{"type": "paragraph", "content": [{"type": "text", "text": text or ""}]}],
    }


class JiraTracker:
    def __init__(self, base_url: str, email: str, token: str, project_key: str) -> None:
        self._base = base_url.rstrip("/")
        self._auth = (email, token)
        self._project = project_key

    async def create_issue(self, summary: str, description: str) -> str | None:
        payload = {
            "fields": {
                "project": {"key": self._project},
                "summary": summary[:255],
                "issuetype": {"name": "Task"},
                "description": _adf(description),
            }
        }
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                f"{self._base}/rest/api/3/issue", auth=self._auth, json=payload
            )
            resp.raise_for_status()
            return resp.json().get("key")

    async def get_status(self, key: str) -> str | None:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{self._base}/rest/api/3/issue/{key}",
                params={"fields": "status"},
                auth=self._auth,
            )
            resp.raise_for_status()
            return resp.json().get("fields", {}).get("status", {}).get("name")

    async def verify(self) -> tuple[bool, str]:
        """Check connectivity and credentials without creating an issue."""
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(f"{self._base}/rest/api/3/myself", auth=self._auth)
                resp.raise_for_status()
                name = resp.json().get("displayName", "unknown")
                return True, f"Connected to Jira as {name}"
        except Exception as exc:  # surface any connectivity/auth failure to the UI
            return False, str(exc)


def build_issue_tracker(settings) -> IssueTracker:
    if not (
        settings.jira_enabled
        and settings.jira_url
        and settings.jira_email
        and settings.jira_api_token
    ):
        return NullTracker()
    return JiraTracker(
        settings.jira_url, settings.jira_email, settings.jira_api_token, settings.jira_project_key
    )


async def get_issue_tracker(session: AsyncSession = Depends(get_session)) -> IssueTracker:
    from .app_settings import effective_settings

    return build_issue_tracker(await effective_settings(session))


def build_change_issue(change: ChangeEvent) -> tuple[str, str]:
    summary = f"PortWiz: {change.change_type} on {change.ip}:{change.port}/{change.protocol}"
    description = (
        f"Confirmed {change.change_type} change on "
        f"{change.ip}:{change.port}/{change.protocol} (severity {change.severity})."
    )
    return summary, description


def build_task_issue(task: Task) -> tuple[str, str]:
    return task.title, (task.description or task.title)


def map_jira_status(name: str | None) -> str | None:
    """Map a Jira status name to a PortWiz task status (best-effort)."""
    if not name:
        return None
    low = name.lower()
    if "progress" in low:
        return "in_progress"
    if any(word in low for word in ("done", "resolved", "closed")):
        return "done"
    if any(word in low for word in ("to do", "open", "backlog", "new")):
        return "open"
    return None


async def link_changes_to_tracker(
    session: AsyncSession, changes: list[ChangeEvent], tracker: IssueTracker
) -> int:
    """Create an issue per confirmed change and store its key on the task."""
    linked = 0
    for change in changes:
        summary, description = build_change_issue(change)
        key = await tracker.create_issue(summary, description)
        if not key:
            continue
        task = (
            await session.execute(select(Task).where(Task.change_event_id == change.id))
        ).scalars().first()
        if task is not None:
            task.jira_key = key
            linked += 1
    if linked:
        await session.commit()
    return linked
