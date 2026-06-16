"""agents.segment and scan_profiles.segment (per-segment routing)

Revision ID: 0008
Revises: 0007
Create Date: 2026-06-16
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("agents", sa.Column("segment", sa.String(length=64), nullable=True))
    op.create_index("ix_agents_segment", "agents", ["segment"])
    op.add_column(
        "scan_profiles", sa.Column("segment", sa.String(length=64), nullable=True)
    )
    op.create_index("ix_scan_profiles_segment", "scan_profiles", ["segment"])


def downgrade() -> None:
    op.drop_index("ix_scan_profiles_segment", table_name="scan_profiles")
    op.drop_column("scan_profiles", "segment")
    op.drop_index("ix_agents_segment", table_name="agents")
    op.drop_column("agents", "segment")
