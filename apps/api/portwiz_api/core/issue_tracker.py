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
    """Talks to either Jira Cloud or Jira Server/Data Center (on-prem).

    The two products diverge in ways that matter to every call, so the
    deployment is resolved once and drives auth, REST version, the description
    format, and the assignee field shape:

    * Cloud   -> REST v3, HTTP basic auth (email + API token), ADF description,
                 assignee by ``accountId``.
    * Server  -> REST v2, bearer Personal Access Token, plain-text description,
                 assignee by ``name`` (username).
    """

    def __init__(
        self,
        base_url: str,
        token: str,
        *,
        deployment: str = "cloud",
        email: str | None = None,
        project_key: str = "PORT",
        issue_type: str = "Task",
        default_assignee: str | None = None,
        labels: str = "",
    ) -> None:
        self._base = base_url.rstrip("/")
        self._cloud = deployment != "server"
        self._token = token
        self._email = email
        self._project = project_key
        self._issue_type = issue_type or "Task"
        self._assignee = default_assignee or None
        self._labels = [x.strip() for x in (labels or "").split(",") if x.strip()]

    @property
    def _api(self) -> str:
        return "3" if self._cloud else "2"

    def _client(self) -> httpx.AsyncClient:
        if self._cloud:
            return httpx.AsyncClient(timeout=15, auth=(self._email or "", self._token))
        # Server/Data Center authenticates a Personal Access Token as a bearer.
        return httpx.AsyncClient(
            timeout=15, headers={"Authorization": f"Bearer {self._token}"}
        )

    def _describe(self, text: str) -> Any:
        # Cloud v3 expects Atlassian Document Format; Server v2 takes plain text.
        return _adf(text) if self._cloud else (text or "")

    def _assignee_field(self) -> dict[str, str] | None:
        if not self._assignee:
            return None
        return {"accountId": self._assignee} if self._cloud else {"name": self._assignee}

    async def create_issue(self, summary: str, description: str) -> str | None:
        fields: dict[str, Any] = {
            "project": {"key": self._project},
            "summary": summary[:255],
            "issuetype": {"name": self._issue_type},
            "description": self._describe(description),
        }
        assignee = self._assignee_field()
        if assignee is not None:
            fields["assignee"] = assignee
        if self._labels:
            fields["labels"] = self._labels
        async with self._client() as client:
            resp = await client.post(
                f"{self._base}/rest/api/{self._api}/issue", json={"fields": fields}
            )
            resp.raise_for_status()
            return resp.json().get("key")

    async def get_status(self, key: str) -> str | None:
        async with self._client() as client:
            resp = await client.get(
                f"{self._base}/rest/api/{self._api}/issue/{key}",
                params={"fields": "status"},
            )
            resp.raise_for_status()
            return resp.json().get("fields", {}).get("status", {}).get("name")

    async def verify(self) -> tuple[bool, str]:
        """Check connectivity and credentials without creating an issue."""
        try:
            async with self._client() as client:
                resp = await client.get(f"{self._base}/rest/api/{self._api}/myself")
                resp.raise_for_status()
                name = resp.json().get("displayName", "unknown")
                return True, f"Connected to Jira as {name}"
        except Exception as exc:  # surface any connectivity/auth failure to the UI
            return False, str(exc)


def build_issue_tracker(settings) -> IssueTracker:
    # Cloud needs an email for basic auth; Server/DC only needs the bearer token.
    cloud = settings.jira_deployment != "server"
    if not (
        settings.jira_enabled
        and settings.jira_url
        and settings.jira_api_token
        and (not cloud or settings.jira_email)
    ):
        return NullTracker()
    return JiraTracker(
        settings.jira_url,
        settings.jira_api_token,
        deployment=settings.jira_deployment,
        email=settings.jira_email,
        project_key=settings.jira_project_key,
        issue_type=settings.jira_issue_type,
        default_assignee=settings.jira_default_assignee,
        labels=settings.jira_labels,
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
