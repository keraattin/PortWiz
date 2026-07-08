"""cve_findings table (CVE enrichment for discovered services)

Revision ID: 0016
Revises: 0015
Create Date: 2026-07-07
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "cve_findings",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("asset_id", sa.Uuid(), sa.ForeignKey("assets.id"), nullable=True),
        sa.Column("ip", sa.String(length=45), nullable=False),
        sa.Column("port", sa.Integer(), nullable=False),
        sa.Column("protocol", sa.String(length=8), nullable=False),
        sa.Column("service", sa.String(length=128), nullable=True),
        sa.Column("version", sa.String(length=256), nullable=True),
        sa.Column("cve_id", sa.String(length=32), nullable=False),
        sa.Column("cvss", sa.Float(), nullable=True),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("url", sa.String(length=255), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_cve_findings_asset_id", "cve_findings", ["asset_id"])
    op.create_index("ix_cve_findings_ip", "cve_findings", ["ip"])
    op.create_index("ix_cve_findings_cve_id", "cve_findings", ["cve_id"])


def downgrade() -> None:
    op.drop_index("ix_cve_findings_cve_id", table_name="cve_findings")
    op.drop_index("ix_cve_findings_ip", table_name="cve_findings")
    op.drop_index("ix_cve_findings_asset_id", table_name="cve_findings")
    op.drop_table("cve_findings")
