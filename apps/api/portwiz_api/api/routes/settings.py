"""Settings and integration status.

Exposes the *non-secret* effective configuration (provider names, hosts, ports,
enabled flags) so operators can see how PortWiz is wired, plus admin-only "test"
actions that exercise each integration (send a test email, ping the AI provider,
verify the Jira connection). Secrets are never returned.

Configuration itself is environment-driven and read-only here; runtime-editable,
database-backed settings are a later concern.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from ... import __version__
from ...core.ai import AIProvider, get_ai_provider
from ...core.config import get_settings
from ...core.issue_tracker import IssueTracker, get_issue_tracker
from ...core.notifications import Notifier, NullNotifier, get_notifier
from ...models.user import User, UserRole
from ...schemas.settings import EmailTestRequest, SettingsStatus, TestResult
from ..deps import get_current_user, require_roles

router = APIRouter(prefix="/settings", tags=["settings"])

AdminDep = require_roles(UserRole.admin)


@router.get("", response_model=SettingsStatus)
async def get_settings_status(_: User = Depends(get_current_user)) -> SettingsStatus:
    s = get_settings()
    ai_model = s.anthropic_model if s.ai_provider == "claude" else s.ollama_model
    ai_configured = s.ai_provider != "none" and (
        s.ai_provider != "claude" or bool(s.anthropic_api_key)
    )
    jira_configured = bool(
        s.jira_enabled and s.jira_url and s.jira_email and s.jira_api_token
    )
    return SettingsStatus(
        app_name=s.app_name,
        environment=s.environment,
        version=__version__,
        ai_provider=s.ai_provider,
        ai_model=ai_model,
        ai_configured=ai_configured,
        email_enabled=s.notifications_enabled,
        smtp_host=s.smtp_host,
        smtp_port=s.smtp_port,
        smtp_from=s.smtp_from,
        email_recipients=list(s.notification_recipients),
        jira_enabled=s.jira_enabled,
        jira_url=s.jira_url,
        jira_project_key=s.jira_project_key,
        jira_configured=jira_configured,
    )


@router.post("/test/ai", response_model=TestResult)
async def test_ai(
    _: User = Depends(AdminDep),
    provider: AIProvider = Depends(get_ai_provider),
) -> TestResult:
    if provider.name == "none":
        return TestResult(ok=False, detail="No AI provider is configured.")
    try:
        reply = await provider.complete(
            "You are a connectivity check. Reply with the single word OK.", "ping"
        )
        return TestResult(ok=True, detail=f"{provider.name}: {reply[:160]}")
    except Exception as exc:
        return TestResult(ok=False, detail=f"{provider.name}: {exc}")


@router.post("/test/email", response_model=TestResult)
async def test_email(
    payload: EmailTestRequest,
    _: User = Depends(AdminDep),
    notifier: Notifier = Depends(get_notifier),
) -> TestResult:
    if isinstance(notifier, NullNotifier):
        return TestResult(ok=False, detail="Email is disabled or SMTP is not configured.")
    recipients = (
        [payload.recipient]
        if payload.recipient
        else list(get_settings().notification_recipients)
    )
    if not recipients:
        return TestResult(
            ok=False,
            detail="No recipient. Provide one or set PORTWIZ_NOTIFICATION_RECIPIENTS.",
        )
    try:
        await notifier.send(
            "PortWiz test email", "This is a PortWiz connectivity test.", recipients
        )
        return TestResult(ok=True, detail=f"Sent to {', '.join(recipients)}")
    except Exception as exc:
        return TestResult(ok=False, detail=str(exc))


@router.post("/test/jira", response_model=TestResult)
async def test_jira(
    _: User = Depends(AdminDep),
    tracker: IssueTracker = Depends(get_issue_tracker),
) -> TestResult:
    ok, detail = await tracker.verify()
    return TestResult(ok=ok, detail=detail)
