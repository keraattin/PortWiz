"""Tests for production configuration guards."""

from __future__ import annotations

import pytest

from portwiz_api.core.config import Settings, check_production_secrets


def _settings(**overrides) -> Settings:
    base = dict(
        environment="production",
        secret_key="a-real-64-char-random-value-not-a-placeholder-000000000000000000",
        encryption_key="a-real-fernet-key-not-a-placeholder-0000000000000000000000000",
    )
    base.update(overrides)
    return Settings(**base)


def test_development_never_blocks() -> None:
    # Dev may keep the insecure defaults; the guard is a no-op.
    check_production_secrets(_settings(environment="development", secret_key="dev-insecure-change-me"))


def test_production_ok_with_real_secrets() -> None:
    check_production_secrets(_settings())  # must not raise


def test_production_rejects_placeholder_secret_key() -> None:
    with pytest.raises(RuntimeError, match="PORTWIZ_SECRET_KEY"):
        check_production_secrets(_settings(secret_key="change-me-generate-a-long-random-string"))


def test_production_rejects_default_secret_key() -> None:
    with pytest.raises(RuntimeError, match="PORTWIZ_SECRET_KEY"):
        check_production_secrets(_settings(secret_key="dev-insecure-change-me"))


def test_production_rejects_missing_encryption_key() -> None:
    with pytest.raises(RuntimeError, match="PORTWIZ_ENCRYPTION_KEY"):
        check_production_secrets(_settings(encryption_key=None))


def test_production_rejects_placeholder_encryption_key() -> None:
    with pytest.raises(RuntimeError, match="PORTWIZ_ENCRYPTION_KEY"):
        check_production_secrets(_settings(encryption_key="change-me-generate-a-fernet-key"))
