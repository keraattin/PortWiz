"""change_events.notified_at (notification dispatch / digest queue marker)

Revision ID: 0020
Revises: 0019
Create Date: 2026-07-18
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0020"
down_revision = "0019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "change_events",
        sa.Column("notified_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_change_events_notified_at", "change_events", ["notified_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_change_events_notified_at", table_name="change_events")
    op.drop_column("change_events", "notified_at")
