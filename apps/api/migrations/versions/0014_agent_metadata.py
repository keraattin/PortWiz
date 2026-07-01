"""agents.version, agents.platform, agents.last_ip (agent-reported metadata)

Revision ID: 0014
Revises: 0013
Create Date: 2026-07-01
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("agents", sa.Column("version", sa.String(length=32), nullable=True))
    op.add_column("agents", sa.Column("platform", sa.String(length=64), nullable=True))
    op.add_column("agents", sa.Column("last_ip", sa.String(length=45), nullable=True))


def downgrade() -> None:
    op.drop_column("agents", "last_ip")
    op.drop_column("agents", "platform")
    op.drop_column("agents", "version")
