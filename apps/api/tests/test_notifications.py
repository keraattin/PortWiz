"""Unit tests for the notification helpers (no DB, SMTP, or network needed)."""

from __future__ import annotations

from types import SimpleNamespace

from portwiz_api.core.notifications import (
    Channel,
    SlackNotifier,
    TeamsNotifier,
    build_change_email,
    build_channels,
    meets_min_severity,
    notify_changes,
)

_CHANGE = {
    "change_type": "opened",
    "ip": "10.0.0.5",
    "port": 443,
    "protocol": "tcp",
    "severity": "high",
}


def _settings(**overrides):
    """A minimal settings stand-in with every field the notifier code reads."""
    base = dict(
        notifications_enabled=False,
        smtp_host="",
        smtp_port=25,
        smtp_from="portwiz@local",
        smtp_use_tls=False,
        smtp_username=None,
        smtp_password=None,
        notification_recipients=[],
        email_min_severity="low",
        email_scan_profiles=[],
        slack_enabled=False,
        slack_webhook_url=None,
        slack_min_severity="low",
        slack_scan_profiles=[],
        teams_enabled=False,
        teams_webhook_url=None,
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
    """A channel scoped to specific profiles ignores changes from others."""
    recorder = _Recorder()
    channels = [Channel(recorder, "low", ["profile-a"])]
    monkeypatch.setattr(
        "portwiz_api.core.notifications.build_channels", lambda settings: channels
    )
    # A different profile is skipped entirely.
    assert await notify_changes([_CHANGE], _settings(), scan_profile_id="profile-b") == 0
    assert recorder.bodies == []
    # The scoped profile fires.
    assert await notify_changes([_CHANGE], _settings(), scan_profile_id="profile-a") == 1
    assert len(recorder.bodies) == 1


async def test_unprofiled_run_skips_profile_scoped_channels(monkeypatch) -> None:
    """An ad-hoc run (no profile) does not match a channel that filters by
    profile, but does reach an unscoped channel."""
    scoped, unscoped = _Recorder(), _Recorder()
    channels = [Channel(scoped, "low", ["profile-a"]), Channel(unscoped, "low", [])]
    monkeypatch.setattr(
        "portwiz_api.core.notifications.build_channels", lambda settings: channels
    )
    dispatched = await notify_changes([_CHANGE], _settings(), scan_profile_id=None)
    assert dispatched == 1
    assert scoped.bodies == [] and len(unscoped.bodies) == 1
