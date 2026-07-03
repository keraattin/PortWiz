"""agents.*_override (per-agent operational-setting overrides)

Revision ID: 0015
Revises: 0014
Create Date: 2026-07-03
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("agents", sa.Column("poll_seconds_override", sa.Integer(), nullable=True))
    op.add_column("agents", sa.Column("online_seconds_override", sa.Integer(), nullable=True))
    op.add_column("agents", sa.Column("rate_limit_pps_override", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("agents", "rate_limit_pps_override")
    op.drop_column("agents", "online_seconds_override")
    op.drop_column("agents", "poll_seconds_override")
