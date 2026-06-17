"""scan_profiles.compliance_framework (cadence tracking)

Revision ID: 0010
Revises: 0009
Create Date: 2026-06-17
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "scan_profiles",
        sa.Column("compliance_framework", sa.String(length=16), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("scan_profiles", "compliance_framework")
