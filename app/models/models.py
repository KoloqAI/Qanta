from __future__ import annotations
import enum
from datetime import datetime
from typing import Any
from sqlalchemy import (
    Boolean, DateTime, Enum, Float, ForeignKey, Integer, String, Text, JSON, func
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, TimestampMixin, generate_uuid


class DeploymentMode(str, enum.Enum):
    PAPER = "paper"
    LIVE = "live"


class ActorType(str, enum.Enum):
    USER = "user"
    AGENT = "agent"
    SYSTEM = "system"
    ASSISTANT = "assistant"


class User(TimestampMixin, Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    cred_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    sessions: Mapped[list[Session]] = relationship(back_populates="user")
    settings: Mapped[UserSettings | None] = relationship(back_populates="user", uselist=False)


class Session(TimestampMixin, Base):
    __tablename__ = "sessions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    user: Mapped[User] = relationship(back_populates="sessions")


class UserSettings(Base):
    __tablename__ = "user_settings"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), primary_key=True)
    appearance: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    risk: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    models: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    user: Mapped[User] = relationship(back_populates="settings")


class Strategy(TimestampMixin, Base):
    __tablename__ = "strategies"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    domain: Mapped[str] = mapped_column(String(100), nullable=False, default="short_term_equity")
    family: Mapped[str] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="draft")
    versions: Mapped[list[StrategyVersion]] = relationship(back_populates="strategy")


class StrategyVersion(TimestampMixin, Base):
    __tablename__ = "strategy_versions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    strategy_id: Mapped[str] = mapped_column(ForeignKey("strategies.id"), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    rules: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    thesis: Mapped[str] = mapped_column(Text, nullable=False)
    dsl_version: Mapped[int] = mapped_column(Integer, default=1)
    author: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    state: Mapped[str] = mapped_column(String(50), nullable=False, default="draft")
    strategy: Mapped[Strategy] = relationship(back_populates="versions")
    backtest_runs: Mapped[list[BacktestRun]] = relationship(back_populates="strategy_version")
    validation_report: Mapped[ValidationReport | None] = relationship(back_populates="strategy_version", uselist=False)
    deployments: Mapped[list[Deployment]] = relationship(back_populates="strategy_version")
    approvals: Mapped[list[Approval]] = relationship(back_populates="strategy_version")


class ResearchRun(TimestampMixin, Base):
    __tablename__ = "research_runs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    goal: Mapped[str] = mapped_column(Text, nullable=False)
    mode: Mapped[str] = mapped_column(String(50), nullable=False, default="scan")
    trials_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending")
    trials: Mapped[list[Trial]] = relationship(back_populates="research_run")


class Trial(TimestampMixin, Base):
    __tablename__ = "trials"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    research_run_id: Mapped[str] = mapped_column(ForeignKey("research_runs.id"), nullable=False)
    params: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    in_sample_sharpe: Mapped[float | None] = mapped_column(Float)
    spec_hash: Mapped[str | None] = mapped_column(String(64))
    research_run: Mapped[ResearchRun] = relationship(back_populates="trials")


class BacktestRun(TimestampMixin, Base):
    __tablename__ = "backtest_runs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    strategy_version_id: Mapped[str] = mapped_column(ForeignKey("strategy_versions.id"), nullable=False)
    window: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    sharpe: Mapped[float] = mapped_column(Float, nullable=False)
    max_dd: Mapped[float] = mapped_column(Float, nullable=False)
    net_edge: Mapped[float] = mapped_column(Float, nullable=False)
    frictionless_edge: Mapped[float] = mapped_column(Float, nullable=False)
    equity_curve: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    n_trades: Mapped[int] = mapped_column(Integer, nullable=False)
    strategy_version: Mapped[StrategyVersion] = relationship(back_populates="backtest_runs")


class ValidationReport(TimestampMixin, Base):
    __tablename__ = "validation_reports"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    strategy_version_id: Mapped[str] = mapped_column(ForeignKey("strategy_versions.id"), unique=True, nullable=False)
    deflated_sharpe: Mapped[float] = mapped_column(Float, nullable=False)
    pbo: Mapped[float] = mapped_column(Float, nullable=False)
    deg_slope: Mapped[float] = mapped_column(Float, nullable=False)
    peer_hit: Mapped[float] = mapped_column(Float, nullable=False)
    n_eff: Mapped[int] = mapped_column(Integer, nullable=False)
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    confidence_curve: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    detail: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    strategy_version: Mapped[StrategyVersion] = relationship(back_populates="validation_report")
    calibrations: Mapped[list[Calibration]] = relationship(back_populates="validation_report")


class Deployment(TimestampMixin, Base):
    __tablename__ = "deployments"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    strategy_version_id: Mapped[str] = mapped_column(ForeignKey("strategy_versions.id"), nullable=False)
    mode: Mapped[DeploymentMode] = mapped_column(Enum(DeploymentMode), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending")
    guardrails: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    capital_budget: Mapped[float | None] = mapped_column(Float)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    strategy_version: Mapped[StrategyVersion] = relationship(back_populates="deployments")
    orders: Mapped[list[Order]] = relationship(back_populates="deployment")


class Order(TimestampMixin, Base):
    __tablename__ = "orders"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    deployment_id: Mapped[str] = mapped_column(ForeignKey("deployments.id"), nullable=False)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    side: Mapped[str] = mapped_column(String(10), nullable=False)
    qty: Mapped[float] = mapped_column(Float, nullable=False)
    order_type: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    deployment: Mapped[Deployment] = relationship(back_populates="orders")
    fills: Mapped[list[Fill]] = relationship(back_populates="order")


class Fill(Base):
    __tablename__ = "fills"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    order_id: Mapped[str] = mapped_column(ForeignKey("orders.id"), nullable=False)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    qty: Mapped[float] = mapped_column(Float, nullable=False)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    order: Mapped[Order] = relationship(back_populates="fills")


class Approval(Base):
    __tablename__ = "approvals"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    strategy_version_id: Mapped[str] = mapped_column(ForeignKey("strategy_versions.id"), nullable=False)
    approved: Mapped[bool] = mapped_column(Boolean, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    strategy_version: Mapped[StrategyVersion] = relationship(back_populates="approvals")


class AuditLogEntry(Base):
    __tablename__ = "audit_log"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    actor: Mapped[ActorType] = mapped_column(Enum(ActorType), nullable=False)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    subject_type: Mapped[str] = mapped_column(String(100), nullable=False)
    subject_id: Mapped[str] = mapped_column(String(36), nullable=False)
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SearchLedgerEntry(Base):
    __tablename__ = "search_ledger"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    spec_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    hypothesis_family: Mapped[str] = mapped_column(String(100), nullable=False)
    data_window: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    model_version: Mapped[str] = mapped_column(String(100), nullable=False)
    result_metrics: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Calibration(Base):
    __tablename__ = "calibration"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    validation_report_id: Mapped[str] = mapped_column(ForeignKey("validation_reports.id"), nullable=False)
    claimed_c: Mapped[float] = mapped_column(Float, nullable=False)
    target_r: Mapped[float] = mapped_column(Float, nullable=False)
    horizon: Mapped[int] = mapped_column(Integer, nullable=False)
    realized_outcome: Mapped[bool | None] = mapped_column(Boolean)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    validation_report: Mapped[ValidationReport] = relationship(back_populates="calibrations")


class EvolutionRun(Base):
    __tablename__ = "evolution_runs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    tier: Mapped[int] = mapped_column(Integer, nullable=False)
    summary: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    meta_lockbox_result: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ArchetypeSource(str, enum.Enum):
    SEED = "seed"
    EVOLVED = "evolved"


class LibraryArchetype(Base):
    __tablename__ = "library_archetypes"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    family: Mapped[str] = mapped_column(String(100), nullable=False)
    horizon: Mapped[str] = mapped_column(String(50), nullable=False)
    thesis: Mapped[str] = mapped_column(Text, nullable=False)
    template: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    scan: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    param_grid: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    source: Mapped[ArchetypeSource] = mapped_column(
        Enum(ArchetypeSource), nullable=False, server_default="seed"
    )
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="unexplored")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    exploration_runs: Mapped[list[ExplorationRun]] = relationship(back_populates="archetype")


class ExplorationRun(Base):
    __tablename__ = "exploration_runs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    archetype_id: Mapped[str] = mapped_column(ForeignKey("library_archetypes.id"), nullable=False)
    budget_spent: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    trials: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    survivors: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    archetype: Mapped[LibraryArchetype] = relationship(back_populates="exploration_runs")
