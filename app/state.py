"""Shared in-memory service singletons for development.

All API routers import from this module so they share state within a
single process.  When persistent storage is added these singletons will
be replaced by proper dependency injection.
"""
from __future__ import annotations

from app.modules.execution.service import PaperBroker, ExecutionRuntimeImpl
from app.modules.risk.service import RiskGateImpl
from app.modules.portfolio.service import AllocatorImpl, PortfolioRiskGateImpl
from app.modules.monitoring.service import MonitoringServiceImpl, AuditLogImpl
from app.modules.evolution.service import EvolutionLoopImpl
from app.modules.notifications.service import NotifierImpl
from app.modules.registry.service import StrategyRegistryImpl
from app.modules.research.service import ShortTermEquityDomain, StrategyAuthorImpl
from app.core.tools.base import ToolRegistry
from app.core.tools.catalog import register_all_tools

# ---------------------------------------------------------------------------
# Service singletons
# ---------------------------------------------------------------------------

risk_gate = RiskGateImpl()
portfolio_gate = PortfolioRiskGateImpl()
broker = PaperBroker()
runtime = ExecutionRuntimeImpl(broker, risk_gate, portfolio_gate)
allocator = AllocatorImpl()
monitoring = MonitoringServiceImpl()
audit_log = AuditLogImpl()
notifier = NotifierImpl()
registry = StrategyRegistryImpl()
evolution = EvolutionLoopImpl(monitoring=monitoring, registry=registry)
domain = ShortTermEquityDomain()
author = StrategyAuthorImpl()
tool_registry = ToolRegistry()
register_all_tools(tool_registry)

# ---------------------------------------------------------------------------
# Configuration constants
# ---------------------------------------------------------------------------

INITIAL_EQUITY = 100_000.0

# ---------------------------------------------------------------------------
# In-memory stores for features not yet backed by a database
# ---------------------------------------------------------------------------

# Deployments: deployment_id -> deployment dict
deployments: dict[str, dict] = {}

# Staged actions awaiting human confirmation: action_id -> action dict
staged_actions: dict[str, dict] = {}

# User appearance preferences: user_id -> settings dict
appearance_prefs: dict[str, dict] = {}

# Validation reports: strategy_id -> report dict
validation_reports: dict[str, dict] = {}
