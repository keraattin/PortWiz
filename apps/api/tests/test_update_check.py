"""Update check: version comparison, GitHub lookup (mocked), caching, gating."""

from __future__ import annotations

import httpx

from portwiz_api.core import update_check
from portwiz_api.core.update_check import get_update_status, is_newer, parse_version, reset_cache


def _settings(**over):
    from portwiz_api.core.config import get_settings

    return get_settings().model_copy(
        update={
            "app_version": "0.19.0",
            "update_check_enabled": True,
            "update_repo": "x/y",
            **over,
        }
    )


def _mock(handler):
    return lambda: httpx.AsyncClient(transport=httpx.MockTransport(handler), timeout=5)


def test_parse_version() -> None:
    assert parse_version("v0.19.0") == (0, 19, 0)
    assert parse_version("0.19.0") == (0, 19, 0)
    assert parse_version("PortWiz 1.2.3 final") == (1, 2, 3)
    assert parse_version("nope") is None


def test_is_newer() -> None:
    assert is_newer("0.20.0", "0.19.0")
    assert is_newer("1.0.0", "0.19.0")
    assert not is_newer("0.19.0", "0.19.0")
    assert not is_newer("0.18.5", "0.19.0")
    assert not is_newer("garbage", "0.19.0")


async def test_update_available(monkeypatch) -> None:
    reset_cache()

    def handler(req):
        if req.url.path.endswith("/releases/latest"):
            return httpx.Response(200, json={"tag_name": "v0.25.0", "html_url": "https://gh/rel"})
        return httpx.Response(404)

    monkeypatch.setattr(update_check, "_client", _mock(handler))
    st = await get_update_status(_settings(app_version="0.19.0"))
    assert st.enabled
    assert st.latest == "0.25.0"
    assert st.update_available
    assert st.url == "https://gh/rel"
    assert st.error is None


async def test_up_to_date(monkeypatch) -> None:
    reset_cache()
    monkeypatch.setattr(
        update_check,
        "_client",
        _mock(lambda req: httpx.Response(200, json={"tag_name": "v0.19.0", "html_url": "u"})),
    )
    st = await get_update_status(_settings(app_version="0.19.0"))
    assert not st.update_available


async def test_tags_fallback_when_no_release(monkeypatch) -> None:
    reset_cache()

    def handler(req):
        if req.url.path.endswith("/releases/latest"):
            return httpx.Response(404, json={})
        if req.url.path.endswith("/tags"):
            return httpx.Response(
                200, json=[{"name": "v0.18.0"}, {"name": "v0.25.0"}, {"name": "v0.19.0"}]
            )
        return httpx.Response(404)

    monkeypatch.setattr(update_check, "_client", _mock(handler))
    st = await get_update_status(_settings(app_version="0.19.0"))
    assert st.latest == "0.25.0"  # highest tag, not the first
    assert st.update_available


async def test_disabled_does_not_call_github() -> None:
    reset_cache()
    st = await get_update_status(_settings(update_check_enabled=False))
    assert not st.enabled
    assert not st.update_available
    assert st.latest is None


async def test_network_error_is_reported(monkeypatch) -> None:
    reset_cache()

    def handler(req):
        raise httpx.ConnectError("boom")

    monkeypatch.setattr(update_check, "_client", _mock(handler))
    st = await get_update_status(_settings())
    assert st.error is not None
    assert not st.update_available
