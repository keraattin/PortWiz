"""Update check: is a newer PortWiz release available?

Asks GitHub for the latest release (falling back to the newest version tag) and
compares it to the running version. Disabled for air-gapped/compliance installs,
since it contacts an external service. The result is cached so GitHub is polled
at most once per interval, never repeatedly on the request path.
"""

from __future__ import annotations

import datetime as dt
import logging
import re
from dataclasses import dataclass

import httpx

from .. import __version__

logger = logging.getLogger("portwiz.update")

_VER_RE = re.compile(r"(\d+)\.(\d+)\.(\d+)")
_TTL = dt.timedelta(hours=6)
# Module-level cache: the last fetched status and when we fetched it.
_cache: dict[str, object] = {"status": None, "at": None}


def _utcnow() -> dt.datetime:
    return dt.datetime.now(tz=dt.timezone.utc)


def parse_version(s: str) -> tuple[int, int, int] | None:
    """Extract (major, minor, patch) from a tag like 'v0.19.0'; None if absent."""
    m = _VER_RE.search(s or "")
    return (int(m[1]), int(m[2]), int(m[3])) if m else None


def is_newer(latest: str, current: str) -> bool:
    lv, cv = parse_version(latest), parse_version(current)
    return lv is not None and cv is not None and lv > cv


@dataclass
class UpdateStatus:
    enabled: bool
    current: str
    latest: str | None
    update_available: bool
    url: str | None
    checked_at: dt.datetime | None
    error: str | None = None
    # Whether one-click apply is available (an updater sidecar is deployed).
    apply_available: bool = False


_APPLY_KEY = "update_requested_at"


async def request_apply(session) -> None:
    """Record a one-click update request. The updater sidecar polls this flag,
    runs `docker compose pull && up -d`, then clears it."""
    from ..models.app_setting import AppSetting

    now = _utcnow()
    row = await session.get(AppSetting, _APPLY_KEY)
    if row is None:
        session.add(AppSetting(key=_APPLY_KEY, value=now.isoformat(), updated_at=now))
    else:
        row.value = now.isoformat()
        row.updated_at = now
    await session.commit()


def current_version(settings) -> str:
    """The running version: the build-injected tag, else the packaged fallback."""
    return (settings.app_version or __version__).lstrip("v")


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=10)


def reset_cache() -> None:
    _cache["status"] = None
    _cache["at"] = None


async def _fetch(settings, current: str, now: dt.datetime) -> UpdateStatus:
    repo = settings.update_repo
    headers = {"Accept": "application/vnd.github+json"}
    try:
        async with _client() as client:
            # Prefer a published Release (carries release notes); fall back to the
            # newest version tag when a repo only tags without cutting Releases.
            resp = await client.get(
                f"https://api.github.com/repos/{repo}/releases/latest", headers=headers
            )
            if resp.status_code == 200:
                data = resp.json()
                latest = (data.get("tag_name") or "").lstrip("v")
                url = data.get("html_url") or f"https://github.com/{repo}/releases"
            else:
                tags = (
                    await client.get(
                        f"https://api.github.com/repos/{repo}/tags", headers=headers
                    )
                ).json()
                versions = [
                    (parse_version(tag.get("name", "")), tag.get("name", ""))
                    for tag in (tags if isinstance(tags, list) else [])
                ]
                versions = [(v, name) for v, name in versions if v is not None]
                if not versions:
                    raise ValueError("no releases or version tags found")
                _, name = max(versions)
                latest = name.lstrip("v")
                url = f"https://github.com/{repo}/releases"
        return UpdateStatus(
            enabled=True,
            current=current,
            latest=latest,
            update_available=is_newer(latest, current),
            url=url,
            checked_at=now,
        )
    except Exception as exc:  # network / rate limit / parse: report, don't crash
        logger.warning("update check failed: %s", exc)
        return UpdateStatus(
            enabled=True,
            current=current,
            latest=None,
            update_available=False,
            url=None,
            checked_at=now,
            error=str(exc),
        )


async def get_update_status(settings, *, force: bool = False) -> UpdateStatus:
    """Cached update status. Returns a disabled status when the check is off.
    `apply_available` is set fresh from settings on every call (never cached)."""
    current = current_version(settings)
    apply = settings.update_apply_enabled
    if not settings.update_check_enabled:
        return UpdateStatus(
            enabled=False,
            current=current,
            latest=None,
            update_available=False,
            url=None,
            checked_at=None,
            apply_available=apply,
        )
    now = _utcnow()
    cached = _cache["status"]
    at = _cache["at"]
    if not force and isinstance(cached, UpdateStatus) and isinstance(at, dt.datetime):
        if now - at < _TTL and cached.error is None:
            cached.apply_available = apply
            return cached
    status = await _fetch(settings, current, now)
    _cache["status"] = status
    _cache["at"] = now
    status.apply_available = apply
    return status
