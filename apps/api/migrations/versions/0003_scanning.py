"""scanning: scan_profiles, scan_runs, observations (TimescaleDB hypertable)

Revision ID: 0003
Revises: 0002
Create Date: 2026-06-12
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS timescaledb")

    op.create_table(
        "scan_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("targets", postgresql.JSONB(), nullable=False),
        sa.Column("ports", sa.String(length=128), nullable=False, server_default="top-1000"),
        sa.Column("scan_type", sa.String(length=16), nullable=False, server_default="connect"),
        sa.Column("service_detection", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("rate_limit_pps", sa.Integer(), nullable=False, server_default="1000"),
        sa.Column(
            "scan_source",
            sa.String(length=32),
            nullable=False,
            server_default="internal-unauthenticated",
        ),
        sa.Column("cron", sa.String(length=64), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_scan_profiles_name", "scan_profiles", ["name"])

    op.create_table(
        "scan_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "scan_profile_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("scan_profiles.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("agent_id", sa.String(length=128), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="pending"),
        sa.Column("scan_source", sa.String(length=32), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "observations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("ts", sa.DateTime(timezone=True), primary_key=True, nullable=False),
        sa.Column(
            "scan_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("scan_runs.id", ondelete="CASCADE"),
            nullable=False,
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
        sa.Column("state", sa.String(length=16), nullable=False),
        sa.Column("service", sa.String(length=128), nullable=True),
        sa.Column("version", sa.String(length=256), nullable=True),
        sa.Column("product", sa.String(length=256), nullable=True),
        sa.Column("banner_sha256", sa.String(length=64), nullable=True),
        sa.Column("fingerprint_confidence", sa.Float(), nullable=True),
    )
    # Convert observations into a TimescaleDB hypertable partitioned on ts.
    op.execute("SELECT create_hypertable('observations', 'ts', if_not_exists => TRUE)")
    op.create_index("ix_observations_ip_port_ts", "observations", ["ip", "port", "ts"])
    op.create_index("ix_observations_scan_run_id", "observations", ["scan_run_id"])


def downgrade() -> None:
    op.drop_table("observations")
    op.drop_table("scan_runs")
    op.drop_index("ix_scan_profiles_name", table_name="scan_profiles")
    op.drop_table("scan_profiles")
