"""Unit tests for the notification helpers (no DB, SMTP, or network needed)."""

from __future__ import annotations

from types import SimpleNamespace

from portwiz_api.core.notifications import (
    SlackNotifier,
    TeamsNotifier,
    build_change_email,
    build_notifiers,
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
        slack_enabled=False,
        slack_webhook_url=None,
        teams_enabled=False,
        teams_webhook_url=None,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


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
    # Single newlines become blank lines so each item renders on its own line.
    assert "line1\n\nline2" in payload["text"]


def test_build_notifiers_selects_configured_channels() -> None:
    assert build_notifiers(_settings()) == []

    # SMTP host but no recipients: nothing to send, so email is skipped.
    assert build_notifiers(_settings(notifications_enabled=True, smtp_host="mail")) == []

    everything = build_notifiers(
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
    kinds = {type(n).__name__ for n in everything}
    assert kinds == {"EmailNotifier", "SlackNotifier", "TeamsNotifier"}


def test_webhook_enabled_without_url_is_skipped() -> None:
    assert build_notifiers(_settings(slack_enabled=True)) == []
    assert build_notifiers(_settings(teams_enabled=True)) == []


async def test_notify_changes_no_channels_returns_zero() -> None:
    assert await notify_changes([_CHANGE], _settings()) == 0


async def test_notify_changes_empty_summaries_returns_zero() -> None:
    settings = _settings(slack_enabled=True, slack_webhook_url="https://hooks.slack.test/x")
    assert await notify_changes([], settings) == 0


async def test_notify_changes_is_best_effort(monkeypatch) -> None:
    """A failing channel is logged and skipped, never raised, and does not
    prevent the remaining channels from receiving the message."""
    sent: list[str] = []

    class Boom:
        async def send(self, subject, body, recipients) -> None:
            raise RuntimeError("webhook 500")

    class Recorder:
        async def send(self, subject, body, recipients) -> None:
            sent.append(subject)

    monkeypatch.setattr(
        "portwiz_api.core.notifications.build_notifiers",
        lambda settings: [Boom(), Recorder()],
    )
    dispatched = await notify_changes([_CHANGE], _settings())
    assert dispatched == 1  # only Recorder succeeded
    assert len(sent) == 1
