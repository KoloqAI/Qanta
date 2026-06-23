"""Rename deployments.capital -> capital_budget

Revision ID: 002_rename_capital
Revises: 001_initial
Create Date: 2026-06-22
"""
from __future__ import annotations

from alembic import op

revision = "002_rename_capital"
down_revision = "001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("deployments", "capital", new_column_name="capital_budget")


def downgrade() -> None:
    op.alter_column("deployments", "capital_budget", new_column_name="capital")
