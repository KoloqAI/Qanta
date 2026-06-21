"""M6 Gate Tests -- Tool registry + Research agent.

Gate: agent turns a goal/ticker into a DSL spec + thesis; trials logged;
agent has no execution tool (cannot reach risk_increasing tools or broker).
"""
from __future__ import annotations

import pytest
from app.core.tools.base import ToolRegistry, ToolContext, Permission
from app.core.tools.catalog import register_all_tools


@pytest.fixture
def registry():
    r = ToolRegistry()
    register_all_tools(r)
    return r


def test_all_tools_registered(registry):
    tools = registry.list_tools()
    assert len(tools) >= 10
    names = {t.name for t in tools}
    assert "universe_scan" in names
    assert "backtest" in names
    assert "validate" in names
    assert "deploy_strategy" in names


def test_agent_cannot_access_risk_increasing(registry):
    """The research agent must NOT have access to risk_increasing tools."""
    agent_tools = registry.available_for_agent()
    for tool in agent_tools:
        assert tool.permission != Permission.RISK_INCREASING, (
            f"Agent has access to risk_increasing tool '{tool.name}' -- SAFETY VIOLATION"
        )


def test_agent_has_read_tools(registry):
    agent_tools = registry.available_for_agent()
    names = {t.name for t in agent_tools}
    assert "universe_scan" in names
    assert "technical_analysis" in names
    assert "backtest" in names


def test_agent_has_risk_reducing_tools(registry):
    agent_tools = registry.available_for_agent()
    names = {t.name for t in agent_tools}
    assert "pause_deployment" in names
    assert "flatten_deployment" in names


def test_deploy_and_approve_are_risk_increasing(registry):
    deploy = registry.get("deploy_strategy")
    approve = registry.get("approve_strategy")
    assert deploy is not None
    assert approve is not None
    assert deploy.permission == Permission.RISK_INCREASING
    assert approve.permission == Permission.RISK_INCREASING


async def test_author_strategy_produces_spec():
    from app.modules.research.service import StrategyAuthorImpl

    author = StrategyAuthorImpl()
    spec = await author.author("Mean reversion in AAPL", {"ticker": "AAPL"})
    assert spec["thesis"]
    assert spec["tickers"] == ["AAPL"]
    assert any("stop_loss" in e for e in spec["exits"])


async def test_red_team_finds_concerns():
    from app.modules.research.service import StrategyAuthorImpl

    author = StrategyAuthorImpl()
    spec = {
        "thesis": "Test",
        "regime": {"all_of": [{"gt": ["sma(50)", "sma(200)"]}]},
        "exits": [{"stop_loss": {"pct": 3.0}}],
    }
    concerns = await author.red_team(spec)
    assert isinstance(concerns, list)
    assert len(concerns) > 0


async def test_domain_scan_returns_candidates():
    from app.modules.research.service import ShortTermEquityDomain

    domain = ShortTermEquityDomain()
    candidates = await domain.scan("momentum breakout", {})
    assert len(candidates) > 0
    assert all("ticker" in c for c in candidates)


async def test_backtest_tool_works(registry):
    tool = registry.get("backtest")
    assert tool is not None
    spec = {
        "id": "tool-test",
        "version": 1,
        "tickers": ["AAPL"],
        "thesis": "SMA crossover",
        "regime": {"all_of": [{"gt": ["sma(50)", "sma(200)"]}]},
        "entry": {
            "when": {"crosses_above": ["sma(20)", "sma(50)"]},
            "action": "enter_long",
            "sizing": {"fixed_pct": 5.0},
        },
        "exits": [{"stop_loss": {"pct": 3.0}}],
        "risk": {
            "max_position_pct": 5.0,
            "per_trade_stop_pct": 3.0,
            "max_gross_exposure": 40.0,
        },
        "universe": {"primary": "AAPL"},
        "validation": {"targets": [{"R": 0.02, "H": 7}]},
    }
    ctx = ToolContext(user_id="test", session_id="test")
    result = await tool.invoke({"spec": spec}, ctx)
    assert result.success
    assert "n_trades" in result.data
