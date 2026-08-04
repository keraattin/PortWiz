"""observations TLS certificate columns (issuer, SANs, validity window, ...)

Revision ID: 0022
Revises: 0021
Create Date: 2026-08-05
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0022"
down_revision = "0021"
branch_labels = None
depends_on = None


_COLUMNS = (
    ("cert_subject_cn", sa.String(length=256)),
    ("cert_issuer", sa.String(length=256)),
    ("cert_sans", postgresql.JSONB()),
    ("cert_not_before", sa.DateTime(timezone=True)),
    ("cert_not_after", sa.DateTime(timezone=True)),
    ("cert_self_signed", sa.Boolean()),
    ("cert_serial", sa.String(length=128)),
    ("cert_sig_alg", sa.String(length=64)),
)


def upgrade() -> None:
    for name, col_type in _COLUMNS:
        op.add_column("observations", sa.Column(name, col_type, nullable=True))
    # Expiry monitoring scans for certificates whose not_after is near/past.
    op.create_index(
        "ix_observations_cert_not_after", "observations", ["cert_not_after"]
    )


def downgrade() -> None:
    op.drop_index("ix_observations_cert_not_after", table_name="observations")
    for name, _ in reversed(_COLUMNS):
        op.drop_column("observations", name)
