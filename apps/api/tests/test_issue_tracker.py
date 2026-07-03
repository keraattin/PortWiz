"""Unit tests for the Jira issue tracker's cloud vs server/DC behaviour.

A MockTransport captures the outgoing request, so no real Jira is needed; the
assertions cover the parts that diverge between the two products: REST version,
description format, assignee field shape, issue type and labels.
"""

from __future__ import annotations

import json

import httpx

from portwiz_api.core.issue_tracker import (
    JiraTracker,
    NullTracker,
    build_issue_tracker,
)


def _capturing_client(captured: list[httpx.Request], body: dict):
    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, json=body)

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def test_cloud_create_issue_payload(monkeypatch) -> None:
    captured: list[httpx.Request] = []
    tracker = JiraTracker(
        "https://acme.atlassian.net/",
        "token",
        deployment="cloud",
        email="ops@acme.io",
        project_key="SEC",
        issue_type="Bug",
        default_assignee="acc-123",
        labels="portwiz, security",
    )
    monkeypatch.setattr(tracker, "_client", lambda: _capturing_client(captured, {"key": "SEC-1"}))

    key = await tracker.create_issue("summary", "body text")

    assert key == "SEC-1"
    req = captured[0]
    assert req.url.path == "/rest/api/3/issue"
    fields = json.loads(req.content)["fields"]
    assert fields["project"]["key"] == "SEC"
    assert fields["issuetype"]["name"] == "Bug"
    assert fields["assignee"] == {"accountId": "acc-123"}
    assert fields["labels"] == ["portwiz", "security"]
    # Cloud v3 expects Atlassian Document Format (a dict), not a plain string.
    assert isinstance(fields["description"], dict)


async def test_server_create_issue_payload(monkeypatch) -> None:
    captured: list[httpx.Request] = []
    tracker = JiraTracker(
        "https://jira.onprem.local",
        "pat",
        deployment="server",
        project_key="OPS",
        issue_type="Incident",
        default_assignee="jsmith",
    )
    monkeypatch.setattr(tracker, "_client", lambda: _capturing_client(captured, {"key": "OPS-7"}))

    key = await tracker.create_issue("summary", "body text")

    assert key == "OPS-7"
    req = captured[0]
    assert req.url.path == "/rest/api/2/issue"
    fields = json.loads(req.content)["fields"]
    assert fields["issuetype"]["name"] == "Incident"
    assert fields["assignee"] == {"name": "jsmith"}
    # Server v2 takes plain text, and no labels were configured.
    assert isinstance(fields["description"], str)
    assert "labels" not in fields


async def test_server_uses_bearer_token() -> None:
    tracker = JiraTracker("https://jira.onprem.local", "pat", deployment="server")
    client = tracker._client()
    try:
        assert client.headers["Authorization"] == "Bearer pat"
    finally:
        await client.aclose()


async def test_get_status_routes_by_api_version(monkeypatch) -> None:
    captured: list[httpx.Request] = []
    tracker = JiraTracker("https://jira.onprem.local", "pat", deployment="server")
    monkeypatch.setattr(
        tracker,
        "_client",
        lambda: _capturing_client(captured, {"fields": {"status": {"name": "Done"}}}),
    )

    status = await tracker.get_status("OPS-7")

    assert status == "Done"
    assert captured[0].url.path == "/rest/api/2/issue/OPS-7"


class _S:
    """Minimal settings stand-in for build_issue_tracker."""

    jira_enabled = True
    jira_deployment = "cloud"
    jira_url = "https://acme.atlassian.net"
    jira_email = "ops@acme.io"
    jira_api_token = "tok"
    jira_project_key = "PORT"
    jira_issue_type = "Task"
    jira_default_assignee = None
    jira_labels = ""
    jira_priority_high = ""
    jira_priority_medium = ""
    jira_priority_low = ""
    jira_extra_fields = ""


async def test_severity_maps_to_priority(monkeypatch) -> None:
    captured: list[httpx.Request] = []
    tracker = JiraTracker(
        "https://acme.atlassian.net",
        "token",
        deployment="cloud",
        email="ops@acme.io",
        priority_map={"high": "Highest", "medium": "", "low": "Low"},
    )
    monkeypatch.setattr(tracker, "_client", lambda: _capturing_client(captured, {"key": "P-1"}))

    await tracker.create_issue("s", "b", severity="high")
    assert json.loads(captured[0].content)["fields"]["priority"] == {"name": "Highest"}

    # A severity with a blank mapping leaves the priority unset (project default).
    await tracker.create_issue("s", "b", severity="medium")
    assert "priority" not in json.loads(captured[1].content)["fields"]

    # No severity at all -> no priority.
    await tracker.create_issue("s", "b")
    assert "priority" not in json.loads(captured[2].content)["fields"]


async def test_extra_fields_merged_into_issue(monkeypatch) -> None:
    captured: list[httpx.Request] = []
    tracker = JiraTracker(
        "https://acme.atlassian.net",
        "token",
        deployment="cloud",
        email="ops@acme.io",
        extra_fields={"customfield_10050": {"value": "Security"}},
    )
    monkeypatch.setattr(tracker, "_client", lambda: _capturing_client(captured, {"key": "P-2"}))

    await tracker.create_issue("s", "b")
    fields = json.loads(captured[0].content)["fields"]
    assert fields["customfield_10050"] == {"value": "Security"}


def test_build_parses_priority_map_and_extra_fields() -> None:
    s = _S()
    s.jira_priority_high = "Highest"
    s.jira_extra_fields = '{"customfield_10050": {"value": "Security"}}'
    tracker = build_issue_tracker(s)
    assert isinstance(tracker, JiraTracker)
    assert tracker._priority_map == {"high": "Highest"}  # blanks dropped
    assert tracker._extra_fields == {"customfield_10050": {"value": "Security"}}


def test_build_ignores_invalid_extra_fields_json() -> None:
    s = _S()
    s.jira_extra_fields = "not json{"
    tracker = build_issue_tracker(s)
    assert isinstance(tracker, JiraTracker)
    assert tracker._extra_fields == {}


def test_build_requires_email_for_cloud_only() -> None:
    cloud = _S()
    cloud.jira_email = None
    assert isinstance(build_issue_tracker(cloud), NullTracker)

    server = _S()
    server.jira_deployment = "server"
    server.jira_email = None
    assert isinstance(build_issue_tracker(server), JiraTracker)


def test_build_returns_null_when_disabled() -> None:
    s = _S()
    s.jira_enabled = False
    assert isinstance(build_issue_tracker(s), NullTracker)
