"""change detection: port_states and change_events

Revision ID: 0005
Revises: 0004
Create Date: 2026-06-12
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "port_states",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "scan_profile_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("scan_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("ip", sa.String(length=45), nullable=False),
        sa.Column("port", sa.Integer(), nullable=False),
        sa.Column("protocol", sa.String(length=8), nullable=False),
        sa.Column("confirmed_state", sa.String(length=8), nullable=False),
        sa.Column("confirmed_service", sa.String(length=128), nullable=True),
        sa.Column("confirmed_version", sa.String(length=256), nullable=True),
        sa.Column("candidate_state", sa.String(length=8), nullable=True),
        sa.Column("candidate_service", sa.String(length=128), nullable=True),
        sa.Column("candidate_version", sa.String(length=256), nullable=True),
        sa.Column("candidate_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_seen_open_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "scan_profile_id", "ip", "port", "protocol", name="uq_port_state_key"
        ),
    )

    op.create_table(
        "change_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "scan_profile_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("scan_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "scan_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("scan_runs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "asset_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("assets.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("ip", sa.String(length=45), nullable=False),
        sa.Column("port", sa.Integer(), nullable=False),
        sa.Column("protocol", sa.String(length=8), nullable=False),
        sa.Column("change_type", sa.String(length=32), nullable=False),
        sa.Column("before", postgresql.JSONB(), nullable=False),
        sa.Column("after", postgresql.JSONB(), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="open"),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_change_events_ip", "change_events", ["ip"])
    op.create_index("ix_change_events_change_type", "change_events", ["change_type"])
    op.create_index("ix_change_events_status", "change_events", ["status"])
    op.create_index(
        "ix_change_events_profile_detected",
        "change_events",
        ["scan_profile_id", "detected_at"],
    )


def downgrade() -> None:
    op.drop_table("change_events")
    op.drop_table("port_states")
