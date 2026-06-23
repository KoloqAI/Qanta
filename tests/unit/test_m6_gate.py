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


@pytest.fixture
def _force_stub_llm(monkeypatch):
    """Force StubLLMProvider so tests are deterministic without real LLM keys."""
    from app.modules.research.service import StubLLMProvider
    monkeypatch.setattr(
        "app.modules.research.service.create_llm_provider",
        lambda: StubLLMProvider(),
    )


@pytest.fixture
def _force_sample_provider(monkeypatch):
    """Force SampleDataProvider so tests never hit real Polygon."""
    from app.modules.data.providers import SampleDataProvider
    monkeypatch.setattr(
        "app.modules.data.providers.create_data_provider",
        lambda: SampleDataProvider(),
    )


async def test_author_tool_produces_ticker_specific_specs(
    registry, _force_stub_llm,
):
    """author_strategy with different tickers produces specs that contain
    the requested ticker, not a hardcoded default."""
    tool = registry.get("author_strategy")
    assert tool is not None
    ctx = ToolContext(user_id="test", session_id="test")

    r1 = await tool.invoke(
        {"thesis": "Momentum breakout", "ticker": "TSLA"}, ctx,
    )
    assert r1.success, r1.error
    assert r1.data["spec"]["tickers"] == ["TSLA"]

    r2 = await tool.invoke(
        {"thesis": "Mean reversion in oversold territory", "ticker": "JPM"}, ctx,
    )
    assert r2.success, r2.error
    assert r2.data["spec"]["tickers"] == ["JPM"]


async def test_author_tool_rejects_bad_spec():
    """A spec missing stop_loss or with unknown primitives is rejected
    at the DSL parse gate."""
    from app.core.dsl.parser import parse_spec

    bad_spec = {
        "id": "",
        "version": 1,
        "tickers": ["AAPL"],
        "thesis": "Test bad spec",
        "regime": {"all_of": [{"gt": ["sma(50)", "sma(200)"]}]},
        "entry": {
            "when": {"crosses_above": ["sma(20)", "sma(50)"]},
            "action": "enter_long",
            "sizing": {"fixed_pct": 5.0},
        },
        "exits": [],  # No stop_loss — must be rejected
        "risk": {
            "max_position_pct": 5.0,
            "per_trade_stop_pct": 3.0,
            "max_gross_exposure": 40.0,
        },
    }
    result = parse_spec(bad_spec)
    assert not result.success
    assert any("stop_loss" in e.message for e in result.errors)


async def test_author_tool_flags_fallback_template(
    registry, _force_stub_llm,
):
    """When no LLM is configured the tool returns is_fallback_template=True."""
    tool = registry.get("author_strategy")
    ctx = ToolContext(user_id="test", session_id="test")
    result = await tool.invoke(
        {"thesis": "RSI reversion in tech", "ticker": "AAPL"}, ctx,
    )
    assert result.success, result.error
    assert result.data["is_fallback_template"] is True


async def test_author_tool_requires_thesis(registry):
    tool = registry.get("author_strategy")
    ctx = ToolContext(user_id="test", session_id="test")
    result = await tool.invoke({"ticker": "AAPL"}, ctx)
    assert not result.success
    assert "thesis" in (result.error or "").lower()


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


# ---------------------------------------------------------------------------
# peer_test tool tests
# ---------------------------------------------------------------------------

_PEER_TEST_SPEC = {
    "id": "peer-test-spec",
    "version": 1,
    "tickers": ["AAPL"],
    "thesis": "SMA crossover for peer testing",
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


def test_peer_test_tool_registered(registry):
    """peer_test is registered and is a READ tool."""
    tool = registry.get("peer_test")
    assert tool is not None
    assert tool.permission == Permission.READ


@pytest.mark.timeout(30)
async def test_peer_test_generalizing_strategy(registry, _force_sample_provider):
    """A strategy that generalizes to correlated peers passes.

    SampleDataProvider produces synthetic data with similar structure
    for all tickers, so a broad SMA crossover should show edge on
    at least some peers.
    """
    tool = registry.get("peer_test")
    ctx = ToolContext(user_id="test", session_id="test")
    result = await tool.invoke({"spec": _PEER_TEST_SPEC}, ctx)
    assert result.success, result.error
    assert result.data["n_peers_tested"] > 0
    assert result.data["sufficient"]
    assert "peer_hit" in result.data


async def test_peer_test_insufficient_data_fails_closed():
    """When no peers have sufficient data, the peer_backtest result
    shows sufficient=False and peer_hit=0.0 (fail closed)."""
    import pandas as pd
    from app.modules.data.peers import peer_backtest
    from app.modules.data.providers import SampleDataProvider

    class EmptyProvider(SampleDataProvider):
        async def bars(self, symbol, start, end, **kw):
            if symbol != "AAPL":
                return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
            return await super().bars(symbol, start, end, **kw)

    from datetime import datetime, timedelta
    as_of = datetime(2024, 6, 1)
    provider = EmptyProvider()
    spec = _make_parsed_spec("AAPL")

    result = await peer_backtest(
        spec=spec,
        peer_tickers=[f"FAKE{i}" for i in range(10)],
        provider=provider,
        as_of=as_of,
    )
    assert not result["sufficient"]
    assert result["peer_hit"] == 0.0
    assert result["n_peers_tested"] == 0


async def test_peer_test_primary_no_data_fails():
    """When the primary ticker has insufficient data, peer selection fails."""
    import pandas as pd
    from app.modules.data.peers import select_correlation_peers
    from app.modules.data.providers import SampleDataProvider, SAMPLE_UNIVERSE
    from datetime import datetime

    class ShortDataProvider(SampleDataProvider):
        async def bars(self, symbol, start, end, **kw):
            if symbol == "NODATA":
                return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
            return await super().bars(symbol, start, end, **kw)

    provider = ShortDataProvider()
    result = await select_correlation_peers(
        primary="NODATA",
        candidates=list(SAMPLE_UNIVERSE),
        provider=provider,
        as_of=datetime(2024, 6, 1),
    )
    assert not result.sufficient
    assert len(result.peers) == 0


# ---------------------------------------------------------------------------
# Harness peer_hit gate tests
# ---------------------------------------------------------------------------


async def test_harness_includes_peer_hit_gate():
    """ValidationReport includes peer_hit in the gates dict."""
    from app.modules.validation.service import ValidationHarnessImpl, GATES_VERSION
    from app.modules.data.providers import SampleDataProvider
    from datetime import datetime, timedelta

    provider = SampleDataProvider()
    as_of = datetime(2024, 6, 1)
    start = as_of - timedelta(days=700)
    bars = await provider.bars("AAPL", start, as_of)

    harness = ValidationHarnessImpl()
    report = await harness.validate(
        _make_parsed_spec("AAPL"),
        bars,
        n_eff=1,
        peer_tickers=["MSFT", "GOOGL", "AMZN", "META", "NVDA",
                       "TSLA", "JPM", "V", "JNJ", "WMT"],
        provider=provider,
        as_of=as_of,
    )
    assert "peer_hit" in report.detail["gates"]
    assert report.gates_version == GATES_VERSION
    assert report.peer_hit >= 0


async def test_harness_no_peers_fails_closed():
    """When no peers are passed, peer_hit gate is False."""
    from app.modules.validation.service import ValidationHarnessImpl
    from app.modules.data.providers import SampleDataProvider
    from datetime import datetime, timedelta

    provider = SampleDataProvider()
    as_of = datetime(2024, 6, 1)
    bars = await provider.bars("AAPL", as_of - timedelta(days=700), as_of)

    harness = ValidationHarnessImpl()
    report = await harness.validate(
        _make_parsed_spec("AAPL"),
        bars,
        n_eff=1,
        peer_tickers=None,
        provider=provider,
        as_of=as_of,
    )
    assert report.detail["gates"]["peer_hit"] is False


def test_stale_report_invalidation():
    """Reports without current gates_version are marked stale."""
    from app.modules.validation.service import invalidate_stale_reports, GATES_VERSION

    reports = {
        "old-strat": {"passed": True, "gates_version": 1},
        "current-strat": {"passed": True, "gates_version": GATES_VERSION},
        "ancient-strat": {"passed": True},
    }
    count = invalidate_stale_reports(reports)
    assert count == 2
    assert reports["old-strat"]["passed"] is False
    assert "stale_reason" in reports["old-strat"]
    assert reports["current-strat"]["passed"] is True
    assert reports["ancient-strat"]["passed"] is False


def _make_parsed_spec(ticker: str):
    """Helper to produce a parsed StrategySpec for testing."""
    from app.core.dsl.parser import parse_spec
    raw = dict(_PEER_TEST_SPEC, tickers=[ticker])
    result = parse_spec(raw)
    assert result.success, [e.message for e in (result.errors or [])]
    return result.spec
