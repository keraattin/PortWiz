"""Settings and integration status.

Exposes the *non-secret* effective configuration (environment defaults overlaid
with DB overrides) plus admin-only editing and "test" actions. Secrets are never
returned: GET reports only whether each secret is set; PATCH ignores blank
secret fields so an existing value is kept.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from ... import __version__
from ...core.ai import (
    PROVIDER_REGISTRY,
    PROVIDERS_BY_ID,
    AIProvider,
    build_ai_provider,
    get_ai_provider,
)
from ...core.app_settings import effective_settings, set_overrides
from ...core.config import Settings
from ...core.db import get_session
from ...core.inventory_source import InventorySource, get_inventory_source
from ...core.issue_tracker import IssueTracker, NullTracker, get_issue_tracker
from ...core.notifications import Notifier, NullNotifier, get_notifier
from ...models.user import User, UserRole
from ...schemas.settings import (
    AiProviderInfo,
    EmailTestRequest,
    JiraProject,
    JiraUser,
    SettingsConfig,
    SettingsConfigUpdate,
    SettingsStatus,
    TestResult,
)
from ..deps import get_current_user, require_roles

router = APIRouter(prefix="/settings", tags=["settings"])

AdminDep = require_roles(UserRole.admin)


def _config_from(s: Settings) -> SettingsConfig:
    return SettingsConfig(
        ai_provider=s.ai_provider,
        ollama_base_url=s.ollama_base_url,
        ollama_model=s.ollama_model,
        anthropic_model=s.anthropic_model,
        anthropic_api_key_set=bool(s.anthropic_api_key),
        compat_base_url=s.compat_base_url,
        compat_model=s.compat_model,
        compat_api_key_set=bool(s.compat_api_key),
        notifications_enabled=s.notifications_enabled,
        smtp_host=s.smtp_host,
        smtp_port=s.smtp_port,
        smtp_from=s.smtp_from,
        smtp_username=s.smtp_username,
        smtp_use_tls=s.smtp_use_tls,
        smtp_password_set=bool(s.smtp_password),
        notification_recipients=list(s.notification_recipients),
        jira_enabled=s.jira_enabled,
        jira_deployment=s.jira_deployment,
        jira_url=s.jira_url,
        jira_email=s.jira_email,
        jira_project_key=s.jira_project_key,
        jira_issue_type=s.jira_issue_type,
        jira_default_assignee=s.jira_default_assignee,
        jira_labels=s.jira_labels,
        jira_api_token_set=bool(s.jira_api_token),
        netbox_enabled=s.netbox_enabled,
        netbox_url=s.netbox_url,
        netbox_writeback_enabled=s.netbox_writeback_enabled,
        netbox_token_set=bool(s.netbox_token),
        change_confirmations=s.change_confirmations,
        agent_online_seconds=s.agent_online_seconds,
        agent_poll_seconds=s.agent_poll_seconds,
        scan_stale_minutes=s.scan_stale_minutes,
        scan_max_attempts=s.scan_max_attempts,
        default_scan_ports=s.default_scan_ports,
        default_scan_type=s.default_scan_type,
        default_service_detection=s.default_service_detection,
        default_scan_rate_limit_pps=s.default_scan_rate_limit_pps,
    )


@router.get("", response_model=SettingsStatus)
async def get_settings_status(
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> SettingsStatus:
    s = await effective_settings(session)
    info = PROVIDERS_BY_ID.get(s.ai_provider)
    if s.ai_provider == "claude":
        ai_model = s.anthropic_model
    elif s.ai_provider == "ollama":
        ai_model = s.ollama_model
    elif info is not None and info.kind == "openai_compat":
        ai_model = s.compat_model or info.default_model
    else:
        ai_model = ""
    # "configured" means a real provider would be built (keys/URLs present).
    ai_configured = build_ai_provider(s).name != "none"
    # Cloud needs an email (basic auth); Server/DC uses a bearer token only.
    jira_configured = bool(
        s.jira_enabled
        and s.jira_url
        and s.jira_api_token
        and (s.jira_deployment != "cloud" or s.jira_email)
    )
    netbox_configured = bool(s.netbox_enabled and s.netbox_url and s.netbox_token)
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
        jira_deployment=s.jira_deployment,
        jira_url=s.jira_url,
        jira_project_key=s.jira_project_key,
        jira_configured=jira_configured,
        netbox_enabled=s.netbox_enabled,
        netbox_url=s.netbox_url,
        netbox_configured=netbox_configured,
        agent_online_seconds=s.agent_online_seconds,
        default_scan_ports=s.default_scan_ports,
        default_scan_type=s.default_scan_type,
        default_service_detection=s.default_service_detection,
    )


@router.get("/ai-providers", response_model=list[AiProviderInfo])
async def get_ai_providers(_: User = Depends(AdminDep)) -> list[AiProviderInfo]:
    """The selectable AI providers and their field defaults (no secrets)."""
    return [
        AiProviderInfo(
            id=p.id,
            label=p.label,
            kind=p.kind,
            default_base_url=p.default_base_url,
            default_model=p.default_model,
            needs_api_key=p.needs_api_key,
            needs_base_url=p.needs_base_url,
            console_url=p.console_url,
        )
        for p in PROVIDER_REGISTRY
    ]


@router.get("/config", response_model=SettingsConfig)
async def get_config(
    _: User = Depends(AdminDep),
    session: AsyncSession = Depends(get_session),
) -> SettingsConfig:
    return _config_from(await effective_settings(session))


@router.patch("/config", response_model=SettingsConfig)
async def update_config(
    payload: SettingsConfigUpdate,
    current_user: User = Depends(AdminDep),
    session: AsyncSession = Depends(get_session),
) -> SettingsConfig:
    await set_overrides(
        session,
        payload.model_dump(exclude_unset=True),
        actor_id=current_user.id,
        actor_email=current_user.email,
    )
    return _config_from(await effective_settings(session))


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
    session: AsyncSession = Depends(get_session),
) -> TestResult:
    if isinstance(notifier, NullNotifier):
        return TestResult(ok=False, detail="Email is disabled or SMTP is not configured.")
    recipients = (
        [payload.recipient]
        if payload.recipient
        else list((await effective_settings(session)).notification_recipients)
    )
    if not recipients:
        return TestResult(
            ok=False,
            detail="No recipient. Provide one or configure notification recipients.",
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


def _require_jira(tracker: IssueTracker) -> None:
    if isinstance(tracker, NullTracker):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Jira is not configured")


@router.get("/jira/projects", response_model=list[JiraProject])
async def list_jira_projects(
    _: User = Depends(AdminDep),
    tracker: IssueTracker = Depends(get_issue_tracker),
) -> list[JiraProject]:
    """Projects visible to the saved credentials, for the project picker."""
    _require_jira(tracker)
    try:
        rows = await tracker.list_projects()
    except Exception as exc:  # connectivity/auth surfaced to the UI
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"Jira error: {exc}") from exc
    return [JiraProject(**r) for r in rows]


@router.get("/jira/users", response_model=list[JiraUser])
async def search_jira_users(
    q: str = "",
    project: str | None = None,
    _: User = Depends(AdminDep),
    tracker: IssueTracker = Depends(get_issue_tracker),
) -> list[JiraUser]:
    """Assignable users for the default-assignee picker."""
    _require_jira(tracker)
    try:
        rows = await tracker.search_assignable_users(q, project)
    except Exception as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"Jira error: {exc}") from exc
    return [JiraUser(**r) for r in rows]


@router.get("/jira/issue-types", response_model=list[str])
async def list_jira_issue_types(
    _: User = Depends(AdminDep),
    tracker: IssueTracker = Depends(get_issue_tracker),
) -> list[str]:
    """Instance-wide issue type names, for the issue-type picker."""
    _require_jira(tracker)
    try:
        return await tracker.list_issue_types()
    except Exception as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"Jira error: {exc}") from exc


@router.post("/test/netbox", response_model=TestResult)
async def test_netbox(
    _: User = Depends(AdminDep),
    source: InventorySource = Depends(get_inventory_source),
) -> TestResult:
    ok, detail = await source.verify()
    return TestResult(ok=ok, detail=detail)
