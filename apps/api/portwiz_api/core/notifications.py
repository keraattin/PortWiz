"""Notifications.

A small provider-agnostic notifier abstraction. Email (SMTP) is the only
backend today; Slack/Teams can implement the same interface later. Config and
the aiosmtplib dependency are imported lazily so importing this module is cheap
and side-effect free.
"""

from __future__ import annotations

import logging
from email.message import EmailMessage
from typing import Any, Protocol

logger = logging.getLogger("portwiz.notifications")


class Notifier(Protocol):
    async def send(self, subject: str, body: str, recipients: list[str]) -> None: ...


class NullNotifier:
    """No-op notifier used when notifications are disabled/unconfigured."""

    async def send(self, subject: str, body: str, recipients: list[str]) -> None:
        return None


class EmailNotifier:
    def __init__(
        self,
        host: str,
        port: int,
        sender: str,
        use_tls: bool,
        username: str | None,
        password: str | None,
    ) -> None:
        self._host = host
        self._port = port
        self._sender = sender
        self._use_tls = use_tls
        self._username = username
        self._password = password

    async def send(self, subject: str, body: str, recipients: list[str]) -> None:
        import aiosmtplib  # imported lazily

        message = EmailMessage()
        message["From"] = self._sender
        message["To"] = ", ".join(recipients)
        message["Subject"] = subject
        message.set_content(body)
        await aiosmtplib.send(
            message,
            hostname=self._host,
            port=self._port,
            use_tls=self._use_tls,
            username=self._username or None,
            password=self._password or None,
        )


def get_notifier() -> Notifier:
    from .config import get_settings

    settings = get_settings()
    if not settings.notifications_enabled or not settings.smtp_host:
        return NullNotifier()
    return EmailNotifier(
        host=settings.smtp_host,
        port=settings.smtp_port,
        sender=settings.smtp_from,
        use_tls=settings.smtp_use_tls,
        username=settings.smtp_username,
        password=settings.smtp_password,
    )


def build_change_email(summaries: list[dict[str, Any]]) -> tuple[str, str]:
    count = len(summaries)
    subject = f"PortWiz: {count} confirmed change{'s' if count != 1 else ''} detected"
    lines = ["PortWiz detected the following confirmed changes:", ""]
    for s in summaries:
        lines.append(
            f"- [{s['severity']}] {s['change_type']} {s['ip']}:{s['port']}/{s['protocol']}"
        )
    return subject, "\n".join(lines)


async def notify_changes(
    summaries: list[dict[str, Any]],
    recipients: list[str],
    notifier: Notifier | None = None,
) -> bool:
    """Send a change-summary email. Returns True if an email was dispatched."""
    if not summaries or not recipients:
        return False
    notifier = notifier or get_notifier()
    subject, body = build_change_email(summaries)
    await notifier.send(subject, body, recipients)
    return True
