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

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from .db import get_session

logger = logging.getLogger("portwiz.notifications")

# Ordering for the global "minimum severity to notify" rule. Change events only
# ever carry low/medium/high; critical is included so a future higher tier still
# clears every threshold.
_SEVERITY_RANK = {"low": 1, "medium": 2, "high": 3, "critical": 4}


def meets_min_severity(severity: str, minimum: str) -> bool:
    """True when ``severity`` is at or above the configured ``minimum``."""
    return _SEVERITY_RANK.get(severity, 1) >= _SEVERITY_RANK.get(minimum, 1)


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


class _WebhookNotifier:
    """Base for chat notifiers that POST a JSON payload to an incoming webhook.
    ``recipients`` is part of the :class:`Notifier` protocol but has no meaning
    for a webhook (the target is the URL) so it is ignored."""

    def __init__(self, webhook_url: str) -> None:
        self._url = webhook_url

    def _payload(self, subject: str, body: str) -> dict[str, Any]:
        raise NotImplementedError

    async def send(self, subject: str, body: str, recipients: list[str]) -> None:
        import httpx  # imported lazily

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(self._url, json=self._payload(subject, body))
            resp.raise_for_status()


class SlackNotifier(_WebhookNotifier):
    """Posts to a Slack incoming webhook. Slack mrkdwn renders ``*bold*`` and
    keeps newlines, so the plain-text summary maps over directly."""

    def _payload(self, subject: str, body: str) -> dict[str, Any]:
        return {"text": f"*{subject}*\n{body}"}


class TeamsNotifier(_WebhookNotifier):
    """Posts a MessageCard to a Microsoft Teams incoming webhook — the format the
    connector accepts. Blank lines separate list items so each renders on its
    own line."""

    def _payload(self, subject: str, body: str) -> dict[str, Any]:
        return {
            "@type": "MessageCard",
            "@context": "https://schema.org/extensions",
            "summary": subject,
            "themeColor": "0076D7",
            "title": subject,
            "text": body.replace("\n", "\n\n"),
        }


def build_notifier(settings) -> Notifier:
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


def build_notifiers(settings) -> list[Notifier]:
    """Every notification channel that is currently enabled and configured.

    Email is included only when recipients exist (an SMTP host with no
    recipients has nowhere to send); Slack/Teams each need their webhook URL.
    """
    out: list[Notifier] = []
    email = build_notifier(settings)
    if not isinstance(email, NullNotifier) and settings.notification_recipients:
        out.append(email)
    if settings.slack_enabled and settings.slack_webhook_url:
        out.append(SlackNotifier(settings.slack_webhook_url))
    if settings.teams_enabled and settings.teams_webhook_url:
        out.append(TeamsNotifier(settings.teams_webhook_url))
    return out


async def get_notifier(session: AsyncSession = Depends(get_session)) -> Notifier:
    from .app_settings import effective_settings

    return build_notifier(await effective_settings(session))


def build_change_email(summaries: list[dict[str, Any]]) -> tuple[str, str]:
    count = len(summaries)
    subject = f"PortWiz: {count} confirmed change{'s' if count != 1 else ''} detected"
    lines = ["PortWiz detected the following confirmed changes:", ""]
    for s in summaries:
        lines.append(
            f"- [{s['severity']}] {s['change_type']} {s['ip']}:{s['port']}/{s['protocol']}"
        )
    return subject, "\n".join(lines)


async def notify_changes(summaries: list[dict[str, Any]], settings) -> int:
    """Fan out a confirmed-change summary to every configured channel.

    Each channel is best-effort: a failing one is logged and skipped, never
    raised, so a broken webhook can't suppress the other channels (or fail the
    ingest that triggered it). Returns the number of channels that accepted it.
    """
    if not summaries:
        return 0
    minimum = getattr(settings, "notify_min_severity", "low")
    summaries = [s for s in summaries if meets_min_severity(s["severity"], minimum)]
    if not summaries:
        return 0
    notifiers = build_notifiers(settings)
    if not notifiers:
        return 0
    subject, body = build_change_email(summaries)
    recipients = list(settings.notification_recipients)
    dispatched = 0
    for notifier in notifiers:
        try:
            await notifier.send(subject, body, recipients)
            dispatched += 1
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "change notification via %s failed: %s", type(notifier).__name__, exc
            )
    return dispatched
