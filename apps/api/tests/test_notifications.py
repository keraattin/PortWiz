"""Unit tests for the notification helpers (no DB, SMTP, or network needed)."""

from __future__ import annotations

import datetime as dt
from types import SimpleNamespace

import httpx
import pytest

from portwiz_api.core.notifications import (
    Channel,
    SlackApiNotifier,
    SlackNotifier,
    TeamsGraphNotifier,
    TeamsNotifier,
    build_change_email,
    build_channels,
    build_slack_notifier,
    build_teams_notifier,
    in_quiet_hours,
    meets_min_severity,
    notify_changes,
)

_CHANGE = {
    "change_type": "opened",
    "ip": "10.0.0.5",
    "port": 443,
    "protocol": "tcp",
    "severity": "high",
    "scan_profile_id": None,
}


def _settings(**overrides):
    """A minimal settings stand-in with every field the notifier code reads."""
    base = dict(
        notifications_enabled=False,
        smtp_host="",
        smtp_port=25,
        smtp_from="portwiz@local",
        smtp_use_tls=False,
        smtp_tls_verify=True,
        smtp_username=None,
        smtp_password=None,
        notification_recipients=[],
        email_min_severity="low",
        email_scan_profiles=[],
        notify_mode="immediate",
        notify_quiet_hours_enabled=False,
        notify_quiet_start="22:00",
        notify_quiet_end="07:00",
        slack_enabled=False,
        slack_transport="webhook",
        slack_webhook_url=None,
        slack_bot_token=None,
        slack_channel=None,
        slack_min_severity="low",
        slack_scan_profiles=[],
        teams_enabled=False,
        teams_transport="webhook",
        teams_webhook_url=None,
        teams_tenant_id=None,
        teams_client_id=None,
        teams_client_secret=None,
        teams_team_id=None,
        teams_channel_id=None,
        teams_min_severity="low",
        teams_scan_profiles=[],
    )
    base.update(overrides)
    return SimpleNamespace(**base)


class _Recorder:
    def __init__(self) -> None:
        self.bodies: list[str] = []

    async def send(self, subject: str, body: str, recipients: list[str]) -> None:
        self.bodies.append(body)


def test_build_change_email_singular() -> None:
    subject, body = build_change_email([_CHANGE])
    assert "1 confirmed change detected" in subject
    assert "[high] opened 10.0.0.5:443/tcp" in body


def test_build_change_email_plural() -> None:
    subject, _ = build_change_email([_CHANGE, _CHANGE])
    assert "2 confirmed changes detected" in subject


def test_slack_payload_uses_mrkdwn() -> None:
    payload = SlackNotifier("https://hooks.slack.test/x")._payload("Subj", "line1\nline2")
    assert payload == {"text": "*Subj*\nline1\nline2"}


def test_teams_payload_is_message_card() -> None:
    payload = TeamsNotifier("https://teams.test/x")._payload("Subj", "line1\nline2")
    assert payload["@type"] == "MessageCard"
    assert payload["title"] == "Subj"
    assert payload["summary"] == "Subj"
    assert "line1\n\nline2" in payload["text"]


def test_meets_min_severity_ordering() -> None:
    assert meets_min_severity("high", "low")
    assert meets_min_severity("medium", "medium")
    assert not meets_min_severity("low", "medium")
    assert not meets_min_severity("medium", "high")
    assert meets_min_severity("critical", "high")


def test_build_channels_selects_configured_channels() -> None:
    assert build_channels(_settings()) == []

    # SMTP host but no recipients: nothing to send, so email is skipped.
    assert build_channels(_settings(notifications_enabled=True, smtp_host="mail")) == []

    channels = build_channels(
        _settings(
            notifications_enabled=True,
            smtp_host="mail",
            notification_recipients=["ops@test.local"],
            slack_enabled=True,
            slack_webhook_url="https://hooks.slack.test/x",
            teams_enabled=True,
            teams_webhook_url="https://teams.test/x",
        )
    )
    kinds = {type(c.notifier).__name__ for c in channels}
    assert kinds == {"EmailNotifier", "SlackNotifier", "TeamsNotifier"}


def test_build_channels_carries_per_channel_rules() -> None:
    channels = build_channels(
        _settings(
            slack_enabled=True,
            slack_webhook_url="https://hooks.slack.test/x",
            slack_min_severity="high",
            slack_scan_profiles=["p1", "p2"],
        )
    )
    assert len(channels) == 1
    assert channels[0].min_severity == "high"
    assert channels[0].scan_profiles == ["p1", "p2"]


def test_webhook_enabled_without_url_is_skipped() -> None:
    assert build_channels(_settings(slack_enabled=True)) == []
    assert build_channels(_settings(teams_enabled=True)) == []


def test_build_notifier_carries_tls_verify() -> None:
    # An internal relay with a self-signed cert is reached by turning verify off.
    from portwiz_api.core.notifications import EmailNotifier, build_notifier

    n = build_notifier(
        _settings(notifications_enabled=True, smtp_host="mail", smtp_tls_verify=False)
    )
    assert isinstance(n, EmailNotifier)
    assert n._verify is False


async def test_email_notifier_passes_validate_certs(monkeypatch) -> None:
    aiosmtplib = pytest.importorskip("aiosmtplib")
    from portwiz_api.core.notifications import EmailNotifier

    captured: dict = {}

    async def fake_send(message, **kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(aiosmtplib, "send", fake_send)
    await EmailNotifier("mail", 25, "from@x", False, None, None, verify=False).send(
        "Subj", "body", ["to@x"]
    )
    assert captured["validate_certs"] is False


def test_slack_bot_transport_uses_api_notifier() -> None:
    # The bot transport builds the token-based API notifier, not a webhook one.
    notifier = build_slack_notifier(
        _settings(
            slack_enabled=True,
            slack_transport="bot",
            slack_bot_token="xoxb-123",
            slack_channel="#alerts",
        )
    )
    assert isinstance(notifier, SlackApiNotifier)


def test_slack_bot_transport_needs_token_and_channel() -> None:
    # A bot transport missing the token or channel is not configured -> None.
    assert build_slack_notifier(
        _settings(slack_enabled=True, slack_transport="bot", slack_bot_token="xoxb-123")
    ) is None
    assert build_slack_notifier(
        _settings(slack_enabled=True, slack_transport="bot", slack_channel="#alerts")
    ) is None
    # A stale webhook URL is ignored while the bot transport is selected.
    assert build_slack_notifier(
        _settings(
            slack_enabled=True,
            slack_transport="bot",
            slack_webhook_url="https://hooks.slack.test/x",
        )
    ) is None


def test_teams_graph_transport_uses_graph_notifier() -> None:
    notifier = build_teams_notifier(
        _settings(
            teams_enabled=True,
            teams_transport="graph",
            teams_tenant_id="t",
            teams_client_id="c",
            teams_client_secret="s",
            teams_team_id="team",
            teams_channel_id="chan",
        )
    )
    assert isinstance(notifier, TeamsGraphNotifier)


def test_teams_graph_transport_needs_all_fields() -> None:
    # Missing any one of the five Graph fields leaves Teams unconfigured.
    assert build_teams_notifier(
        _settings(
            teams_enabled=True,
            teams_transport="graph",
            teams_tenant_id="t",
            teams_client_id="c",
            teams_client_secret="s",
            teams_team_id="team",
            # teams_channel_id missing
        )
    ) is None


def test_bot_and_graph_transports_flow_through_build_channels() -> None:
    channels = build_channels(
        _settings(
            slack_enabled=True,
            slack_transport="bot",
            slack_bot_token="xoxb-123",
            slack_channel="#alerts",
            teams_enabled=True,
            teams_transport="graph",
            teams_tenant_id="t",
            teams_client_id="c",
            teams_client_secret="s",
            teams_team_id="team",
            teams_channel_id="chan",
        )
    )
    kinds = {type(c.notifier).__name__ for c in channels}
    assert kinds == {"SlackApiNotifier", "TeamsGraphNotifier"}


def _patch_httpx(monkeypatch, handler) -> list[httpx.Request]:
    """Route the notifier's internally-created httpx client through a mock
    transport, returning the list that captures each request it makes."""
    captured: list[httpx.Request] = []

    def capturing(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return handler(request)

    real_client = httpx.AsyncClient

    def fake_client(*args, **kwargs):
        kwargs.pop("timeout", None)
        return real_client(transport=httpx.MockTransport(capturing))

    monkeypatch.setattr(httpx, "AsyncClient", fake_client)
    return captured


async def test_slack_api_notifier_posts_to_chat_postmessage(monkeypatch) -> None:
    captured = _patch_httpx(
        monkeypatch, lambda req: httpx.Response(200, json={"ok": True})
    )
    await SlackApiNotifier("xoxb-123", "#alerts").send("Subj", "line1\nline2", [])
    assert len(captured) == 1
    assert str(captured[0].url) == "https://slack.com/api/chat.postMessage"
    assert captured[0].headers["authorization"] == "Bearer xoxb-123"


async def test_slack_api_notifier_raises_on_logical_error(monkeypatch) -> None:
    # Slack returns HTTP 200 with ok:false on logical failures; that must raise
    # so a channel error is surfaced, not silently swallowed.
    _patch_httpx(
        monkeypatch,
        lambda req: httpx.Response(200, json={"ok": False, "error": "channel_not_found"}),
    )
    with pytest.raises(RuntimeError, match="channel_not_found"):
        await SlackApiNotifier("xoxb-123", "#nope").send("Subj", "body", [])


async def test_teams_graph_notifier_fetches_token_then_posts(monkeypatch) -> None:
    # Two calls: the token endpoint, then the Graph channel-messages endpoint with
    # the bearer token attached.
    def handler(req: httpx.Request) -> httpx.Response:
        if "login.microsoftonline.com" in req.url.host:
            return httpx.Response(200, json={"access_token": "gtok"})
        return httpx.Response(201, json={"id": "1"})

    captured = _patch_httpx(monkeypatch, handler)
    await TeamsGraphNotifier("t", "c", "s", "team", "chan").send("Subj", "b", [])
    assert len(captured) == 2
    assert "oauth2/v2.0/token" in str(captured[0].url)
    assert "teams/team/channels/chan/messages" in str(captured[1].url)
    assert captured[1].headers["authorization"] == "Bearer gtok"


async def test_notify_changes_no_channels_returns_zero() -> None:
    assert await notify_changes([_CHANGE], _settings()) == 0


async def test_notify_changes_empty_summaries_returns_zero() -> None:
    settings = _settings(slack_enabled=True, slack_webhook_url="https://hooks.slack.test/x")
    assert await notify_changes([], settings) == 0


async def test_notify_changes_is_best_effort(monkeypatch) -> None:
    """A failing channel is logged and skipped, never raised, and does not
    prevent the remaining channels from receiving the message."""
    recorder = _Recorder()

    class Boom:
        async def send(self, subject, body, recipients) -> None:
            raise RuntimeError("webhook 500")

    channels = [Channel(Boom(), "low", []), Channel(recorder, "low", [])]
    monkeypatch.setattr(
        "portwiz_api.core.notifications.build_channels", lambda settings: channels
    )
    dispatched = await notify_changes([_CHANGE], _settings())
    assert dispatched == 1  # only the recorder succeeded
    assert len(recorder.bodies) == 1


async def test_notify_changes_applies_per_channel_severity(monkeypatch) -> None:
    """Each channel filters by its own min severity, independently."""
    email, slack = _Recorder(), _Recorder()
    channels = [Channel(email, "low", []), Channel(slack, "high", [])]
    monkeypatch.setattr(
        "portwiz_api.core.notifications.build_channels", lambda settings: channels
    )
    low = {**_CHANGE, "severity": "low", "port": 21}
    high = {**_CHANGE, "severity": "high", "port": 443}
    dispatched = await notify_changes([low, high], _settings())
    assert dispatched == 2
    assert ":21/" in email.bodies[0] and ":443/" in email.bodies[0]  # low channel: both
    assert ":443/" in slack.bodies[0] and ":21/" not in slack.bodies[0]  # high: only high


async def test_notify_changes_respects_channel_profile_scope(monkeypatch) -> None:
    """A channel scoped to specific profiles ignores changes from others, using
    each summary's own scan_profile_id."""
    recorder = _Recorder()
    channels = [Channel(recorder, "low", ["profile-a"])]
    monkeypatch.setattr(
        "portwiz_api.core.notifications.build_channels", lambda settings: channels
    )
    # A different profile is skipped entirely.
    assert await notify_changes([{**_CHANGE, "scan_profile_id": "profile-b"}], _settings()) == 0
    assert recorder.bodies == []
    # The scoped profile fires.
    assert await notify_changes([{**_CHANGE, "scan_profile_id": "profile-a"}], _settings()) == 1
    assert len(recorder.bodies) == 1


async def test_notify_changes_mixed_profiles_in_one_digest(monkeypatch) -> None:
    """One call spanning profiles: a scoped channel takes only its profile's
    changes; an unscoped channel takes all of them."""
    scoped, unscoped = _Recorder(), _Recorder()
    channels = [Channel(scoped, "low", ["profile-a"]), Channel(unscoped, "low", [])]
    monkeypatch.setattr(
        "portwiz_api.core.notifications.build_channels", lambda settings: channels
    )
    a = {**_CHANGE, "scan_profile_id": "profile-a", "port": 22}
    b = {**_CHANGE, "scan_profile_id": "profile-b", "port": 443}
    dispatched = await notify_changes([a, b], _settings())
    assert dispatched == 2
    assert ":22/" in scoped.bodies[0] and ":443/" not in scoped.bodies[0]  # only its own
    assert ":22/" in unscoped.bodies[0] and ":443/" in unscoped.bodies[0]  # both


def test_in_quiet_hours_disabled_is_never_quiet() -> None:
    now = dt.datetime(2026, 1, 1, 23, 0, tzinfo=dt.timezone.utc)
    assert not in_quiet_hours(now, _settings())


def test_in_quiet_hours_overnight_window() -> None:
    s = _settings(
        notify_quiet_hours_enabled=True, notify_quiet_start="22:00", notify_quiet_end="07:00"
    )
    assert in_quiet_hours(dt.datetime(2026, 1, 1, 23, 0, tzinfo=dt.timezone.utc), s)
    assert in_quiet_hours(dt.datetime(2026, 1, 1, 3, 0, tzinfo=dt.timezone.utc), s)
    assert not in_quiet_hours(dt.datetime(2026, 1, 1, 12, 0, tzinfo=dt.timezone.utc), s)


def test_in_quiet_hours_daytime_window() -> None:
    s = _settings(
        notify_quiet_hours_enabled=True, notify_quiet_start="09:00", notify_quiet_end="17:00"
    )
    assert in_quiet_hours(dt.datetime(2026, 1, 1, 12, 0, tzinfo=dt.timezone.utc), s)
    assert not in_quiet_hours(dt.datetime(2026, 1, 1, 20, 0, tzinfo=dt.timezone.utc), s)


def test_in_quiet_hours_malformed_window_is_not_quiet() -> None:
    s = _settings(
        notify_quiet_hours_enabled=True, notify_quiet_start="", notify_quiet_end="07:00"
    )
    assert not in_quiet_hours(dt.datetime(2026, 1, 1, 3, 0, tzinfo=dt.timezone.utc), s)
