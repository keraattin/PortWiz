"""Notifications.

A small provider-agnostic notifier abstraction. Email (SMTP) is the only
backend today; Slack/Teams can implement the same interface later. Config and
the aiosmtplib dependency are imported lazily so importing this module is cheap
and side-effect free.
"""

from __future__ import annotations

import datetime as dt
import logging
from dataclasses import dataclass
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


def _parse_hhmm(value: str) -> dt.time | None:
    try:
        hh, mm = value.strip().split(":")
        return dt.time(int(hh), int(mm))
    except (ValueError, AttributeError):
        return None


def in_quiet_hours(now: dt.datetime, settings) -> bool:
    """True when ``now`` (UTC) falls inside the configured quiet-hours window.

    Windows that wrap past midnight (start later than end) are handled. A blank,
    malformed, or zero-length window counts as "not quiet".
    """
    if not settings.notify_quiet_hours_enabled:
        return False
    start = _parse_hhmm(settings.notify_quiet_start)
    end = _parse_hhmm(settings.notify_quiet_end)
    if start is None or end is None or start == end:
        return False
    cur = now.hour * 60 + now.minute
    s = start.hour * 60 + start.minute
    e = end.hour * 60 + end.minute
    if s < e:
        return s <= cur < e
    return cur >= s or cur < e


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
    """Posts a MessageCard to a Microsoft Teams incoming webhook, the format the
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


@dataclass
class Channel:
    """A configured delivery channel plus its own delivery rules: notify only at
    or above ``min_severity`` and only for ``scan_profiles`` (empty = all)."""

    notifier: Notifier
    min_severity: str
    scan_profiles: list[str]


def build_channels(settings) -> list[Channel]:
    """Every notification channel that is currently enabled and configured, each
    paired with its per-channel delivery rules.

    Email is included only when recipients exist (an SMTP host with no
    recipients has nowhere to send); Slack/Teams each need their webhook URL.
    """
    out: list[Channel] = []
    email = build_notifier(settings)
    if not isinstance(email, NullNotifier) and settings.notification_recipients:
        out.append(
            Channel(
                email,
                settings.email_min_severity,
                list(settings.email_scan_profiles),
            )
        )
    if settings.slack_enabled and settings.slack_webhook_url:
        out.append(
            Channel(
                SlackNotifier(settings.slack_webhook_url),
                settings.slack_min_severity,
                list(settings.slack_scan_profiles),
            )
        )
    if settings.teams_enabled and settings.teams_webhook_url:
        out.append(
            Channel(
                TeamsNotifier(settings.teams_webhook_url),
                settings.teams_min_severity,
                list(settings.teams_scan_profiles),
            )
        )
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
    """Fan out confirmed-change summaries to every configured channel, applying
    each channel's own delivery rules (min severity and scan-profile scope).

    Each summary carries its own ``scan_profile_id`` so one call may span several
    profiles (as a digest does); a channel scoped to specific profiles only
    receives the changes it lists. Each channel is best-effort: a failing one is
    logged and skipped, never raised, so a broken webhook can't suppress the
    others (or fail the ingest that triggered it). Returns the number of
    channels that accepted a message.
    """
    if not summaries:
        return 0
    channels = build_channels(settings)
    if not channels:
        return 0
    recipients = list(settings.notification_recipients)
    dispatched = 0
    for ch in channels:
        # Per change: severity must clear the channel's bar, and (when the
        # channel filters by profile) the change's profile must be listed.
        selected = [
            s
            for s in summaries
            if meets_min_severity(s["severity"], ch.min_severity)
            and (not ch.scan_profiles or s.get("scan_profile_id") in ch.scan_profiles)
        ]
        if not selected:
            continue
        subject, body = build_change_email(selected)
        try:
            await ch.notifier.send(subject, body, recipients)
            dispatched += 1
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "change notification via %s failed: %s", type(ch.notifier).__name__, exc
            )
    return dispatched
