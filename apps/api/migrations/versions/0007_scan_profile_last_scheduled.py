"""scan_profiles.last_scheduled_at

Revision ID: 0007
Revises: 0006
Create Date: 2026-06-13
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "scan_profiles",
        sa.Column("last_scheduled_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("scan_profiles", "last_scheduled_at")
