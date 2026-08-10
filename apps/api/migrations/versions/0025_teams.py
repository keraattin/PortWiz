"""teams, team_members, and owner_team_id on assets and vlans

Revision ID: 0025
Revises: 0024
Create Date: 2026-08-10
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0025"
down_revision = "0024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "teams",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_teams_name", "teams", ["name"], unique=True)

    op.create_table(
        "team_members",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("team_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.UniqueConstraint("team_id", "user_id", name="uq_team_member"),
    )

    op.add_column("assets", sa.Column("owner_team_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_assets_owner_team", "assets", "teams", ["owner_team_id"], ["id"]
    )
    op.add_column("vlans", sa.Column("owner_team_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_vlans_owner_team", "vlans", "teams", ["owner_team_id"], ["id"]
    )


def downgrade() -> None:
    op.drop_constraint("fk_vlans_owner_team", "vlans", type_="foreignkey")
    op.drop_column("vlans", "owner_team_id")
    op.drop_constraint("fk_assets_owner_team", "assets", type_="foreignkey")
    op.drop_column("assets", "owner_team_id")
    op.drop_table("team_members")
    op.drop_index("ix_teams_name", table_name="teams")
    op.drop_table("teams")
