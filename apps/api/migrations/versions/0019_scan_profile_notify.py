"""scan_profiles.notify_enabled (per-profile notification opt-out)

Revision ID: 0019
Revises: 0018
Create Date: 2026-07-17
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "scan_profiles",
        sa.Column(
            "notify_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
    )


def downgrade() -> None:
    op.drop_column("scan_profiles", "notify_enabled")
