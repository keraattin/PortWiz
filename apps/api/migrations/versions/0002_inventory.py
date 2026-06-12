"""asset inventory: vlans, ip_ranges, assets

Revision ID: 0002
Revises: 0001
Create Date: 2026-06-12
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "vlans",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("vlan_tag", sa.Integer(), nullable=True),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_vlans_name", "vlans", ["name"], unique=True)

    op.create_table(
        "ip_ranges",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("cidr", sa.String(length=64), nullable=False),
        sa.Column(
            "vlan_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("vlans.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_ip_ranges_cidr", "ip_ranges", ["cidr"])

    op.create_table(
        "assets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("ip", sa.String(length=45), nullable=False),
        sa.Column("hostname", sa.String(length=255), nullable=True),
        sa.Column(
            "vlan_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("vlans.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "owner_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("criticality", sa.String(length=16), nullable=False, server_default="medium"),
        sa.Column("data_sensitivity", sa.String(length=16), nullable=False, server_default="none"),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_assets_ip", "assets", ["ip"])
    op.create_index("ix_assets_vlan_id", "assets", ["vlan_id"])
    op.create_index("ix_assets_owner_id", "assets", ["owner_id"])


def downgrade() -> None:
    op.drop_table("assets")
    op.drop_table("ip_ranges")
    op.drop_index("ix_vlans_name", table_name="vlans")
    op.drop_table("vlans")
