"""Immutable, hash-chained audit log.

Every security-relevant action is appended as an :class:`AuditEvent` whose hash
chains to the previous event's hash. Any tampering (insert, update, delete, or
reorder) breaks the chain and is detectable via :func:`verify_chain`.

Appends are serialized with a PostgreSQL transaction-level advisory lock so the
chain head is read and extended atomically under concurrency. On non-PostgreSQL
backends (e.g. SQLite in unit tests) the lock is skipped.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import uuid
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.audit import AuditEvent

# 64 hex zeros: the predecessor hash of the very first event.
GENESIS_HASH = "0" * 64

# Stable advisory-lock key (fits in a signed bigint). Derived from "PWZAUDIT".
_AUDIT_LOCK_KEY = 5_796_120_949_146_519_873


def canonical_payload(payload: dict[str, Any]) -> str:
    """Deterministic JSON encoding used as hash input."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def compute_event_hash(
    *,
    prev_hash: str,
    actor_email: str | None,
    action: str,
    target_type: str | None,
    target_id: str | None,
    created_at: dt.datetime,
    payload: dict[str, Any],
) -> str:
    """Compute the SHA-256 hash that links an event to its predecessor."""
    # Normalize to aware UTC. SQLite (used in tests) drops tzinfo on
    # DateTime(timezone=True), so a value read back is naive; we always store
    # UTC, so treat a naive value as UTC. Without this, the write-side (aware)
    # and verify-side (naive) hashes diverge whenever the local zone is not UTC.
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=dt.timezone.utc)
    hasher = hashlib.sha256()
    parts = [
        prev_hash,
        actor_email or "",
        action,
        target_type or "",
        target_id or "",
        created_at.astimezone(dt.timezone.utc).isoformat(),
        canonical_payload(payload),
    ]
    hasher.update("\x1f".join(parts).encode("utf-8"))
    return hasher.hexdigest()


async def _is_postgres(session: AsyncSession) -> bool:
    return session.get_bind().dialect.name == "postgresql"


async def append_audit(
    session: AsyncSession,
    *,
    action: str,
    actor_id: uuid.UUID | None = None,
    actor_email: str | None = None,
    target_type: str | None = None,
    target_id: str | None = None,
    payload: dict[str, Any] | None = None,
) -> AuditEvent:
    """Append a new event to the audit chain.

    The caller is responsible for committing the surrounding transaction.
    """
    payload = payload or {}

    if await _is_postgres(session):
        await session.execute(
            text("SELECT pg_advisory_xact_lock(:k)"), {"k": _AUDIT_LOCK_KEY}
        )

    last = (
        await session.execute(
            select(AuditEvent).order_by(AuditEvent.seq.desc()).limit(1)
        )
    ).scalar_one_or_none()
    prev_hash = last.hash if last else GENESIS_HASH

    created_at = dt.datetime.now(tz=dt.timezone.utc)
    event_hash = compute_event_hash(
        prev_hash=prev_hash,
        actor_email=actor_email,
        action=action,
        target_type=target_type,
        target_id=target_id,
        created_at=created_at,
        payload=payload,
    )

    event = AuditEvent(
        actor_id=actor_id,
        actor_email=actor_email,
        action=action,
        target_type=target_type,
        target_id=target_id,
        payload=payload,
        prev_hash=prev_hash,
        hash=event_hash,
        created_at=created_at,
    )
    session.add(event)
    await session.flush()
    return event


async def verify_chain(session: AsyncSession) -> tuple[bool, int | None]:
    """Recompute the whole chain.

    Returns ``(True, None)`` if intact, otherwise ``(False, seq)`` where ``seq``
    is the first event whose stored hash or linkage does not match.
    """
    events = (
        await session.execute(select(AuditEvent).order_by(AuditEvent.seq.asc()))
    ).scalars().all()

    prev_hash = GENESIS_HASH
    for event in events:
        if event.prev_hash != prev_hash:
            return False, event.seq
        recomputed = compute_event_hash(
            prev_hash=event.prev_hash,
            actor_email=event.actor_email,
            action=event.action,
            target_type=event.target_type,
            target_id=event.target_id,
            created_at=event.created_at,
            payload=event.payload,
        )
        if recomputed != event.hash:
            return False, event.seq
        prev_hash = event.hash

    return True, None
