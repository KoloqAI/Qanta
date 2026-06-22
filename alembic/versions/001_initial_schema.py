"""Initial schema - all tables

Revision ID: 001_initial
Revises: (none)
Create Date: 2026-06-21
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "001_initial"
down_revision = None
branch_labels = None
depends_on = None

# ---- Enum types used across tables ----
deployment_mode_enum = sa.Enum("paper", "live", name="deploymentmode")
actor_type_enum = sa.Enum("user", "agent", "system", "assistant", name="actortype")


def upgrade() -> None:
    # -- 1. users (no FK deps) --
    op.create_table(
        "users",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("email", sa.String(255), unique=True, nullable=False),
        sa.Column("cred_hash", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )

    # -- 2. sessions (FK -> users) --
    op.create_table(
        "sessions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("token_hash", sa.String(255), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )

    # -- 3. user_settings (PK = FK -> users, no TimestampMixin) --
    op.create_table(
        "user_settings",
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("appearance", sa.JSON, nullable=True),
        sa.Column("risk", sa.JSON, nullable=True),
        sa.Column("models", sa.JSON, nullable=True),
    )

    # -- 4. strategies (FK -> users) --
    op.create_table(
        "strategies",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("domain", sa.String(100), nullable=False, server_default="short_term_equity"),
        sa.Column("family", sa.String(100), nullable=True),
        sa.Column("status", sa.String(50), nullable=False, server_default="draft"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )

    # -- 5. strategy_versions (FK -> strategies) --
    op.create_table(
        "strategy_versions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("strategy_id", sa.String(36), sa.ForeignKey("strategies.id"), nullable=False),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("rules", sa.JSON, nullable=False),
        sa.Column("thesis", sa.Text, nullable=False),
        sa.Column("dsl_version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("author", sa.JSON, nullable=True),
        sa.Column("state", sa.String(50), nullable=False, server_default="draft"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )

    # -- 6. research_runs (FK -> users) --
    op.create_table(
        "research_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("goal", sa.Text, nullable=False),
        sa.Column("mode", sa.String(50), nullable=False, server_default="scan"),
        sa.Column("trials_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("status", sa.String(50), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )

    # -- 7. trials (FK -> research_runs) --
    op.create_table(
        "trials",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("research_run_id", sa.String(36), sa.ForeignKey("research_runs.id"), nullable=False),
        sa.Column("params", sa.JSON, nullable=False),
        sa.Column("in_sample_sharpe", sa.Float, nullable=True),
        sa.Column("spec_hash", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )

    # -- 8. backtest_runs (FK -> strategy_versions) --
    op.create_table(
        "backtest_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("strategy_version_id", sa.String(36), sa.ForeignKey("strategy_versions.id"), nullable=False),
        sa.Column("window", sa.JSON, nullable=False),
        sa.Column("sharpe", sa.Float, nullable=False),
        sa.Column("max_dd", sa.Float, nullable=False),
        sa.Column("net_edge", sa.Float, nullable=False),
        sa.Column("frictionless_edge", sa.Float, nullable=False),
        sa.Column("equity_curve", sa.JSON, nullable=False),
        sa.Column("n_trades", sa.Integer, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )

    # -- 9. validation_reports (FK -> strategy_versions, unique constraint) --
    op.create_table(
        "validation_reports",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("strategy_version_id", sa.String(36), sa.ForeignKey("strategy_versions.id"), unique=True, nullable=False),
        sa.Column("deflated_sharpe", sa.Float, nullable=False),
        sa.Column("pbo", sa.Float, nullable=False),
        sa.Column("deg_slope", sa.Float, nullable=False),
        sa.Column("peer_hit", sa.Float, nullable=False),
        sa.Column("n_eff", sa.Integer, nullable=False),
        sa.Column("passed", sa.Boolean, nullable=False),
        sa.Column("confidence_curve", sa.JSON, nullable=True),
        sa.Column("detail", sa.JSON, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )

    # -- 10. deployments (FK -> strategy_versions, uses DeploymentMode enum) --
    op.create_table(
        "deployments",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("strategy_version_id", sa.String(36), sa.ForeignKey("strategy_versions.id"), nullable=False),
        sa.Column("mode", deployment_mode_enum, nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="pending"),
        sa.Column("guardrails", sa.JSON, nullable=True),
        sa.Column("capital", sa.Float, nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )

    # -- 11. orders (FK -> deployments) --
    op.create_table(
        "orders",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("deployment_id", sa.String(36), sa.ForeignKey("deployments.id"), nullable=False),
        sa.Column("symbol", sa.String(20), nullable=False),
        sa.Column("side", sa.String(10), nullable=False),
        sa.Column("qty", sa.Float, nullable=False),
        sa.Column("order_type", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("ts", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )

    # -- 12. fills (FK -> orders, no TimestampMixin) --
    op.create_table(
        "fills",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("order_id", sa.String(36), sa.ForeignKey("orders.id"), nullable=False),
        sa.Column("price", sa.Float, nullable=False),
        sa.Column("qty", sa.Float, nullable=False),
        sa.Column("ts", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # -- 13. approvals (FK -> users, FK -> strategy_versions, no TimestampMixin) --
    op.create_table(
        "approvals",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("strategy_version_id", sa.String(36), sa.ForeignKey("strategy_versions.id"), nullable=False),
        sa.Column("approved", sa.Boolean, nullable=False),
        sa.Column("reason", sa.Text, nullable=True),
        sa.Column("ts", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # -- 14. audit_log (FK -> users nullable, uses ActorType enum, no TimestampMixin) --
    op.create_table(
        "audit_log",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("actor", actor_type_enum, nullable=False),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("subject_type", sa.String(100), nullable=False),
        sa.Column("subject_id", sa.String(36), nullable=False),
        sa.Column("payload", sa.JSON, nullable=True),
        sa.Column("ts", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # -- 15. search_ledger (no FKs, no TimestampMixin) --
    op.create_table(
        "search_ledger",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("spec_hash", sa.String(64), nullable=False),
        sa.Column("hypothesis_family", sa.String(100), nullable=False),
        sa.Column("data_window", sa.JSON, nullable=False),
        sa.Column("model_version", sa.String(100), nullable=False),
        sa.Column("result_metrics", sa.JSON, nullable=False),
        sa.Column("ts", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # -- 16. calibration (FK -> validation_reports, no TimestampMixin) --
    op.create_table(
        "calibration",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("validation_report_id", sa.String(36), sa.ForeignKey("validation_reports.id"), nullable=False),
        sa.Column("claimed_c", sa.Float, nullable=False),
        sa.Column("target_r", sa.Float, nullable=False),
        sa.Column("horizon", sa.Integer, nullable=False),
        sa.Column("realized_outcome", sa.Boolean, nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
    )

    # -- 17. evolution_runs (no FKs, no TimestampMixin) --
    op.create_table(
        "evolution_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tier", sa.Integer, nullable=False),
        sa.Column("summary", sa.JSON, nullable=True),
        sa.Column("meta_lockbox_result", sa.JSON, nullable=True),
        sa.Column("ts", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    # Drop tables in reverse dependency order.
    # Independent / leaf tables first, then work back to root tables.
    op.drop_table("evolution_runs")
    op.drop_table("calibration")
    op.drop_table("search_ledger")
    op.drop_table("audit_log")
    op.drop_table("approvals")
    op.drop_table("fills")
    op.drop_table("orders")
    op.drop_table("deployments")
    op.drop_table("validation_reports")
    op.drop_table("backtest_runs")
    op.drop_table("trials")
    op.drop_table("research_runs")
    op.drop_table("strategy_versions")
    op.drop_table("strategies")
    op.drop_table("user_settings")
    op.drop_table("sessions")
    op.drop_table("users")

    # Drop enum types after tables that use them are gone.
    actor_type_enum.drop(op.get_bind(), checkfirst=True)
    deployment_mode_enum.drop(op.get_bind(), checkfirst=True)
