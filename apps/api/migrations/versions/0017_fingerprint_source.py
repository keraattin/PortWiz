"""observations.fingerprint_source (service-detection provenance)

Revision ID: 0017
Revises: 0016
Create Date: 2026-07-08
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "observations",
        sa.Column("fingerprint_source", sa.String(length=16), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("observations", "fingerprint_source")
