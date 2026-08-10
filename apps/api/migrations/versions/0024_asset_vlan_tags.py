"""tags on vlans and assets (free-form labels for grouping/filtering)

Revision ID: 0024
Revises: 0023
Create Date: 2026-08-10
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0024"
down_revision = "0023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("vlans", sa.Column("tags", postgresql.JSONB(), nullable=True))
    op.add_column("assets", sa.Column("tags", postgresql.JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("assets", "tags")
    op.drop_column("vlans", "tags")
