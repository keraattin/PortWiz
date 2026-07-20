"""Backfill change_events.notified_at for pre-existing rows

Revision ID: 0021
Revises: 0020
Create Date: 2026-07-20

Changes that predate the notification-dispatch marker (0020) were already handled
under the old immediate-only path. Mark them processed (notified_at = detected_at)
so the digest flush does not treat all of history as pending and re-notify it on
its first run after upgrade. New rows keep defaulting to NULL and flow through the
normal disposition logic.
"""

from __future__ import annotations

from alembic import op

revision = "0021"
down_revision = "0020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "UPDATE change_events SET notified_at = detected_at WHERE notified_at IS NULL"
    )


def downgrade() -> None:
    # One-way data backfill: backfilled rows are indistinguishable from genuinely
    # dispatched ones, so there is nothing to reverse.
    pass
