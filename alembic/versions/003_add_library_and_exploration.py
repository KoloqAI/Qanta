"""Add library_archetypes and exploration_runs tables

Revision ID: 003_library_exploration
Revises: 002_rename_capital
Create Date: 2026-06-22
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "003_library_exploration"
down_revision = "002_rename_capital"
branch_labels = None
depends_on = None

archetype_source_enum = sa.Enum("seed", "evolved", name="archetypesource")


def upgrade() -> None:
    op.create_table(
        "library_archetypes",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("family", sa.String(100), nullable=False),
        sa.Column("horizon", sa.String(50), nullable=False),
        sa.Column("thesis", sa.Text, nullable=False),
        sa.Column("template", sa.JSON, nullable=False),
        sa.Column("scan", sa.JSON, nullable=False),
        sa.Column("param_grid", sa.JSON, nullable=False),
        sa.Column("source", archetype_source_enum, nullable=False, server_default="seed"),
        sa.Column("status", sa.String(50), nullable=False, server_default="unexplored"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "exploration_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "archetype_id",
            sa.String(36),
            sa.ForeignKey("library_archetypes.id"),
            nullable=False,
        ),
        sa.Column("budget_spent", sa.Float, nullable=False, server_default="0"),
        sa.Column("trials", sa.Integer, nullable=False, server_default="0"),
        sa.Column("survivors", sa.Integer, nullable=False, server_default="0"),
        sa.Column("ts", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("exploration_runs")
    op.drop_table("library_archetypes")
    archetype_source_enum.drop(op.get_bind(), checkfirst=True)
