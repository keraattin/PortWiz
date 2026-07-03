"""Issue tracker integration (Jira).

A provider-agnostic interface so other trackers (ServiceNow, GitHub Issues)
can be added later. ``get_issue_tracker`` is a FastAPI dependency, which also
makes it trivial to inject a fake in tests. Config is imported lazily.
"""

from __future__ import annotations

import json
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
    async def create_issue(
        self, summary: str, description: str, *, severity: str | None = None
    ) -> str | None: ...
    async def get_status(self, key: str) -> str | None: ...
    async def verify(self) -> tuple[bool, str]: ...
    async def list_projects(self) -> list[dict[str, str]]: ...
    async def search_assignable_users(
        self, query: str, project: str | None
    ) -> list[dict[str, str]]: ...
    async def list_issue_types(self) -> list[str]: ...
    async def list_priorities(self) -> list[str]: ...


class NullTracker:
    """Used when no tracker is configured. Every operation is a no-op."""

    async def create_issue(
        self, summary: str, description: str, *, severity: str | None = None
    ) -> str | None:
        return None

    async def get_status(self, key: str) -> str | None:
        return None

    async def verify(self) -> tuple[bool, str]:
        return False, "Jira is not configured."

    async def list_projects(self) -> list[dict[str, str]]:
        return []

    async def search_assignable_users(
        self, query: str, project: str | None
    ) -> list[dict[str, str]]:
        return []

    async def list_issue_types(self) -> list[str]:
        return []

    async def list_priorities(self) -> list[str]:
        return []


def _adf(text: str) -> dict[str, Any]:
    """Minimal Atlassian Document Format wrapper for a plain-text description."""
    return {
        "type": "doc",
        "version": 1,
        "content": [{"type": "paragraph", "content": [{"type": "text", "text": text or ""}]}],
    }


def _user_label(user: dict[str, Any]) -> str:
    """A human label for an assignable user: display name plus email when known."""
    name = user.get("displayName") or user.get("name") or "unknown"
    email = user.get("emailAddress")
    return f"{name} ({email})" if email else name


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
        priority_map: dict[str, str] | None = None,
        extra_fields: dict[str, Any] | None = None,
    ) -> None:
        self._base = base_url.rstrip("/")
        self._cloud = deployment != "server"
        self._token = token
        self._email = email
        self._project = project_key
        self._issue_type = issue_type or "Task"
        self._assignee = default_assignee or None
        self._labels = [x.strip() for x in (labels or "").split(",") if x.strip()]
        # severity -> Jira priority name; only non-blank entries are applied.
        self._priority_map = {k: v for k, v in (priority_map or {}).items() if v}
        self._extra_fields = extra_fields or {}

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

    async def create_issue(
        self, summary: str, description: str, *, severity: str | None = None
    ) -> str | None:
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
        priority = self._priority_map.get((severity or "").lower())
        if priority:
            fields["priority"] = {"name": priority}
        # Admin-supplied custom fields override anything above (they win on key clash).
        fields.update(self._extra_fields)
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

    async def list_projects(self) -> list[dict[str, str]]:
        """Projects the credentials can see, for the project picker."""
        async with self._client() as client:
            if self._cloud:
                resp = await client.get(
                    f"{self._base}/rest/api/3/project/search", params={"maxResults": 100}
                )
                resp.raise_for_status()
                values = resp.json().get("values", [])
            else:
                resp = await client.get(f"{self._base}/rest/api/2/project")
                resp.raise_for_status()
                values = resp.json()
        return [
            {"key": p.get("key", ""), "name": p.get("name", "")}
            for p in values
            if p.get("key")
        ]

    async def search_assignable_users(
        self, query: str, project: str | None
    ) -> list[dict[str, str]]:
        """Users assignable on a project, for the default-assignee picker. The
        identifier differs by deployment: accountId (Cloud) vs username (Server)."""
        proj = project or self._project
        async with self._client() as client:
            if self._cloud:
                resp = await client.get(
                    f"{self._base}/rest/api/3/user/assignable/search",
                    params={"project": proj, "query": query or "", "maxResults": 50},
                )
                resp.raise_for_status()
                return [
                    {"id": u.get("accountId", ""), "label": _user_label(u)}
                    for u in resp.json()
                    if u.get("accountId")
                ]
            resp = await client.get(
                f"{self._base}/rest/api/2/user/assignable/search",
                params={"project": proj, "username": query or "", "maxResults": 50},
            )
            resp.raise_for_status()
            return [
                {"id": u.get("name", ""), "label": _user_label(u)}
                for u in resp.json()
                if u.get("name")
            ]

    async def list_issue_types(self) -> list[str]:
        """Instance-wide issue type names (sub-tasks excluded), for the picker.
        Not project-scoped; an out-of-scheme pick simply errors at create time."""
        async with self._client() as client:
            resp = await client.get(f"{self._base}/rest/api/{self._api}/issuetype")
            resp.raise_for_status()
            types = resp.json()
        names: list[str] = []
        seen: set[str] = set()
        for it in types:
            if it.get("subtask"):
                continue
            name = it.get("name")
            if name and name not in seen:
                seen.add(name)
                names.append(name)
        return names

    async def list_priorities(self) -> list[str]:
        """Instance-wide priority names, for the severity-to-priority pickers."""
        async with self._client() as client:
            resp = await client.get(f"{self._base}/rest/api/{self._api}/priority")
            resp.raise_for_status()
            return [p["name"] for p in resp.json() if p.get("name")]


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
        priority_map={
            "high": settings.jira_priority_high,
            "medium": settings.jira_priority_medium,
            "low": settings.jira_priority_low,
        },
        extra_fields=_parse_extra_fields(settings.jira_extra_fields),
    )


def _parse_extra_fields(raw: str) -> dict[str, Any]:
    """Parse the admin's extra-fields JSON, tolerating blank or malformed input."""
    if not (raw or "").strip():
        return {}
    try:
        data = json.loads(raw)
    except (ValueError, TypeError):
        logger.warning("Ignoring invalid jira_extra_fields JSON.")
        return {}
    return data if isinstance(data, dict) else {}


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
        key = await tracker.create_issue(summary, description, severity=change.severity)
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
