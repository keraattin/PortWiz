"""Unit tests for the notification helpers (no DB or SMTP needed)."""

from __future__ import annotations

from portwiz_api.core.notifications import NullNotifier, build_change_email, notify_changes

_CHANGE = {
    "change_type": "opened",
    "ip": "10.0.0.5",
    "port": 443,
    "protocol": "tcp",
    "severity": "high",
}


def test_build_change_email_singular() -> None:
    subject, body = build_change_email([_CHANGE])
    assert "1 confirmed change detected" in subject
    assert "[high] opened 10.0.0.5:443/tcp" in body


def test_build_change_email_plural() -> None:
    subject, _ = build_change_email([_CHANGE, _CHANGE])
    assert "2 confirmed changes detected" in subject


async def test_notify_skips_without_recipients() -> None:
    sent = await notify_changes([_CHANGE], recipients=[], notifier=NullNotifier())
    assert sent is False


async def test_notify_dispatches_to_notifier() -> None:
    class Collector:
        def __init__(self) -> None:
            self.sent: list[tuple[str, list[str]]] = []

        async def send(self, subject: str, body: str, recipients: list[str]) -> None:
            self.sent.append((subject, recipients))

    collector = Collector()
    sent = await notify_changes([_CHANGE], recipients=["a@b.local"], notifier=collector)
    assert sent is True
    assert len(collector.sent) == 1
    assert collector.sent[0][1] == ["a@b.local"]
