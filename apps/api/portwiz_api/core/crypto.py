"""At-rest encryption for secret settings.

Secret values stored in ``app_settings`` are encrypted with Fernet (AES-128-CBC
+ HMAC) when an encryption key is configured. Ciphertext is stored with a
versioned prefix so a read can tell encrypted values from legacy plaintext, and
migration is lazy: a value is re-encrypted the next time it is written.

The ``cryptography`` import is lazy so that, with no key configured, the module
works as a pass-through even where the package is absent (e.g. a not-yet-rebuilt
container). Failures fail closed: an unreadable secret decrypts to "" rather
than leaking ciphertext into an integration.
"""

from __future__ import annotations

import logging

logger = logging.getLogger("portwiz.crypto")

# Bump the version if the scheme changes; old values stay readable by their tag.
_PREFIX = "enc:v1:"


def is_encrypted(stored: str | None) -> bool:
    return bool(stored) and stored.startswith(_PREFIX)


def _fernet(key: str | None):
    if not key:
        return None
    try:
        from cryptography.fernet import Fernet

        return Fernet(key.encode("utf-8"))
    except Exception as exc:  # invalid key or missing package: fall back to plaintext
        logger.error("Encryption unavailable (%s); secrets handled as plaintext.", exc)
        return None


def encrypt_secret(value: str, key: str | None) -> str:
    """Encrypt a secret for storage. Without a usable key the value is returned
    unchanged, so data written before a key was set stays compatible."""
    if not value:
        return value
    fernet = _fernet(key)
    if fernet is None:
        return value
    token = fernet.encrypt(value.encode("utf-8")).decode("utf-8")
    return f"{_PREFIX}{token}"


def decrypt_secret(stored: str, key: str | None) -> str:
    """Decrypt a stored secret. Legacy plaintext (no prefix) is returned as-is.
    An encrypted value with no usable key, or a wrong key, fails closed to ""."""
    if not is_encrypted(stored):
        return stored
    fernet = _fernet(key)
    if fernet is None:
        logger.error("Encrypted secret present but no usable encryption key.")
        return ""
    try:
        return fernet.decrypt(stored[len(_PREFIX) :].encode("utf-8")).decode("utf-8")
    except Exception:  # wrong key / corrupted token
        logger.error("Failed to decrypt a stored secret (wrong key?).")
        return ""
