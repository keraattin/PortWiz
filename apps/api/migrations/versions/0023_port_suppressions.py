"""port_suppressions (false-positive ports hidden from views and alerts)

Revision ID: 0023
Revises: 0022
Create Date: 2026-08-05
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0023"
down_revision = "0022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "port_suppressions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("ip", sa.String(length=45), nullable=False),
        sa.Column("port", sa.Integer(), nullable=False),
        sa.Column("protocol", sa.String(length=8), nullable=False),
        sa.Column("reason", sa.String(length=256), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.UniqueConstraint("ip", "port", "protocol", name="uq_port_suppression_key"),
    )


def downgrade() -> None:
    op.drop_table("port_suppressions")
