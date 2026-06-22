"""Unit tests for at-rest secret encryption."""

from __future__ import annotations

from cryptography.fernet import Fernet

from portwiz_api.core.crypto import decrypt_secret, encrypt_secret, is_encrypted


def _key() -> str:
    return Fernet.generate_key().decode()


def test_round_trip_with_key() -> None:
    key = _key()
    enc = encrypt_secret("sk-secret-value", key)
    assert is_encrypted(enc)
    assert "sk-secret-value" not in enc  # ciphertext, not plaintext
    assert decrypt_secret(enc, key) == "sk-secret-value"


def test_no_key_is_passthrough() -> None:
    assert encrypt_secret("sk-secret", None) == "sk-secret"
    assert decrypt_secret("sk-secret", None) == "sk-secret"


def test_legacy_plaintext_decrypts_to_itself() -> None:
    # A value written before encryption was enabled has no prefix and must read
    # back unchanged, even with a key now configured.
    key = _key()
    assert decrypt_secret("legacy-plaintext", key) == "legacy-plaintext"


def test_empty_value_unchanged() -> None:
    key = _key()
    assert encrypt_secret("", key) == ""
    assert decrypt_secret("", key) == ""


def test_wrong_key_fails_closed() -> None:
    enc = encrypt_secret("sk-secret", _key())
    assert decrypt_secret(enc, _key()) == ""  # different key -> empty, not garbage


def test_encrypted_without_key_fails_closed() -> None:
    enc = encrypt_secret("sk-secret", _key())
    assert decrypt_secret(enc, None) == ""
