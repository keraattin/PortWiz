"""scan agents

Revision ID: 0004
Revises: 0003
Create Date: 2026-06-12
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_agents_name", "agents", ["name"], unique=True)
    op.create_index("ix_agents_token_hash", "agents", ["token_hash"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_agents_token_hash", table_name="agents")
    op.drop_index("ix_agents_name", table_name="agents")
    op.drop_table("agents")
