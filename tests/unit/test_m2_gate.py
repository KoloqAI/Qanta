"""M2 Gate Tests — Data + Backtest

Gate requirements from docs/06:
  1. Backtest a hand-written spec
  2. Frictionless vs net edge both reported
  3. A seeded lookahead test is detected/blocked
"""
from __future__ import annotations

import pytest
import pandas as pd
import numpy as np
from datetime import datetime

from app.core.dsl.schema import StrategySpec, RiskEnvelope
from app.core.dsl.interpreter import interpret
from app.modules.backtest.service import BacktesterImpl, CostModel, BacktestResult
from app.modules.data.providers import SampleDataProvider
from app.modules.data.features import FeatureComputer
from app.modules.data.lookahead import LookaheadGuard, LookaheadError


def _make_spec() -> StrategySpec:
    """Hand-written SMA crossover spec for gate testing."""
    return StrategySpec(
        id="m2-gate-test",
        version=1,
        tickers=["AAPL"],
        thesis="SMA crossover: buy when fast SMA crosses above slow SMA in uptrend",
        regime={
            "all_of": [
                {"gt": ["sma(50)", "sma(200)"]},
            ]
        },
        entry={
            "when": {"crosses_above": ["sma(20)", "sma(50)"]},
            "action": "enter_long",
            "sizing": {"fixed_pct": 5.0},
        },
        exits=[
            {"stop_loss": {"pct": 3.0}},
            {"take_profit": {"pct": 6.0}},
        ],
        risk=RiskEnvelope(
            max_position_pct=10.0,
            per_trade_stop_pct=3.0,
            max_gross_exposure=40.0,
        ),
        universe={"primary": "AAPL"},
        validation={"targets": [{"R": 0.02, "H": 10}]},
    )


@pytest.fixture
async def bars() -> pd.DataFrame:
    """Generate 2 years of deterministic OHLCV via SampleDataProvider."""
    provider = SampleDataProvider()
    return await provider.bars("AAPL", datetime(2020, 1, 1), datetime(2022, 1, 1))


# ---------- Gate 1: Backtest a hand-written spec ----------

@pytest.mark.asyncio
async def test_backtest_hand_written_spec():
    """A hand-written SMA crossover spec produces a valid BacktestResult."""
    provider = SampleDataProvider()
    bars = await provider.bars("AAPL", datetime(2020, 1, 1), datetime(2022, 1, 1))
    spec = _make_spec()

    bt = BacktesterImpl(initial_capital=100_000.0)
    result = await bt.run(spec, bars)

    assert isinstance(result, BacktestResult)
    assert result.n_trades >= 0
    assert len(result.equity_curve) == len(bars)
    assert result.equity_curve[0]["equity"] == 100_000.0


@pytest.mark.asyncio
async def test_interpreter_produces_valid_signals():
    """The interpreter produces the expected signal columns."""
    provider = SampleDataProvider()
    bars = await provider.bars("AAPL", datetime(2020, 1, 1), datetime(2022, 1, 1))
    spec = _make_spec()

    signals = interpret(spec, bars)

    assert len(signals) == len(bars)
    assert set(signals.columns) == {"signal", "regime_active", "stop_loss", "take_profit", "position_size_pct"}
    assert signals["signal"].isin([0, 1, -1]).all()
    assert signals["regime_active"].dtype == bool


# ---------- Gate 2: Frictionless vs net edge both reported ----------

@pytest.mark.asyncio
async def test_frictionless_vs_net_edge_reported():
    """Both frictionless_edge and net_edge are present and net <= frictionless."""
    provider = SampleDataProvider()
    bars = await provider.bars("AAPL", datetime(2020, 1, 1), datetime(2022, 1, 1))
    spec = _make_spec()

    bt = BacktesterImpl(initial_capital=100_000.0)
    result = await bt.run(spec, bars)

    assert hasattr(result, "frictionless_edge")
    assert hasattr(result, "net_edge")

    if result.n_trades > 0:
        assert result.net_edge <= result.frictionless_edge, (
            f"Net edge ({result.net_edge}) should be <= frictionless ({result.frictionless_edge}) "
            "because transaction costs reduce returns"
        )


@pytest.mark.asyncio
async def test_cost_model_reduces_edge():
    """High friction costs produce lower net_edge than zero-cost run."""
    provider = SampleDataProvider()
    bars = await provider.bars("AAPL", datetime(2020, 1, 1), datetime(2022, 1, 1))
    spec = _make_spec()
    bt = BacktesterImpl(initial_capital=100_000.0)

    zero_cost = CostModel(commission_per_share=0.0, spread_bps=0.0, slippage_bps=0.0)
    high_cost = CostModel(commission_per_share=0.01, spread_bps=20.0, slippage_bps=10.0)

    result_zero = await bt.run(spec, bars, costs=zero_cost)
    result_high = await bt.run(spec, bars, costs=high_cost)

    if result_zero.n_trades > 0:
        assert result_high.net_edge <= result_zero.net_edge, (
            "Higher costs should produce equal or lower net edge"
        )


# ---------- Gate 3: Seeded lookahead test detected/blocked ----------

def test_lookahead_guard_detects_future_bars():
    """LookaheadGuard.check_bars raises when bars contain future data."""
    dates = pd.bdate_range("2023-01-02", periods=100)
    bars = pd.DataFrame(
        {
            "open": np.random.default_rng(42).uniform(90, 110, 100),
            "high": np.random.default_rng(42).uniform(100, 120, 100),
            "low": np.random.default_rng(42).uniform(80, 100, 100),
            "close": np.random.default_rng(42).uniform(90, 110, 100),
            "volume": np.random.default_rng(42).integers(1_000_000, 10_000_000, 100).astype(float),
        },
        index=dates,
    )

    as_of = pd.Timestamp("2023-03-15")
    future_bars = bars[bars.index > as_of]
    assert len(future_bars) > 0, "Test setup: should have bars after as_of"

    with pytest.raises(LookaheadError, match="future data points"):
        LookaheadGuard.check_bars(bars, as_of)


def test_lookahead_guard_passes_clean_bars():
    """LookaheadGuard.check_bars passes when all bars are before as_of."""
    dates = pd.bdate_range("2023-01-02", periods=50)
    bars = pd.DataFrame(
        {
            "open": np.ones(50) * 100,
            "high": np.ones(50) * 105,
            "low": np.ones(50) * 95,
            "close": np.ones(50) * 100,
            "volume": np.ones(50) * 1_000_000,
        },
        index=dates,
    )

    as_of = pd.Timestamp("2024-01-01")
    result = LookaheadGuard.check_bars(bars, as_of)
    assert len(result) == 50


@pytest.mark.asyncio
async def test_provider_enforces_point_in_time():
    """SampleDataProvider.bars() clamps data to as_of — no future leak."""
    provider = SampleDataProvider()
    as_of = datetime(2021, 6, 1)

    bars = await provider.bars(
        "AAPL",
        start=datetime(2020, 1, 1),
        end=datetime(2022, 1, 1),
        as_of=as_of,
    )

    if len(bars) > 0:
        last_date = bars.index[-1]
        assert last_date <= pd.Timestamp(as_of), (
            f"Last bar date {last_date} is after as_of {as_of} — point-in-time violation"
        )


@pytest.mark.asyncio
async def test_universe_survivorship_free():
    """Universe includes delisted symbols before their delist date, excludes after."""
    provider = SampleDataProvider()

    before = await provider.universe(as_of=datetime(2022, 1, 1))
    assert "DELIST1" in before, "DELIST1 should be in universe before its delist date (2022-06-15)"

    after = await provider.universe(as_of=datetime(2023, 12, 1))
    assert "DELIST1" not in after, "DELIST1 should NOT be in universe after its delist date"
    assert "DELIST2" not in after, "DELIST2 should NOT be in universe after its delist date"


# ---------- Feature computation sanity ----------

def test_sma_correctness():
    """SMA produces correct values on a known series."""
    series = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])
    sma3 = FeatureComputer.sma(series, 3)
    assert np.isnan(sma3.iloc[0])
    assert np.isnan(sma3.iloc[1])
    assert sma3.iloc[2] == pytest.approx(2.0)
    assert sma3.iloc[3] == pytest.approx(3.0)
    assert sma3.iloc[4] == pytest.approx(4.0)


def test_rsi_bounded():
    """RSI values should be in [0, 100]."""
    rng = np.random.default_rng(99)
    prices = pd.Series(100 * np.exp(np.cumsum(rng.normal(0, 0.01, 200))))
    rsi = FeatureComputer.rsi(prices, 14)
    valid = rsi.dropna()
    assert (valid >= 0).all() and (valid <= 100).all()


# ---------- Backtest determinism ----------

@pytest.mark.asyncio
async def test_backtest_deterministic():
    """Same spec + same bars = identical result (no randomness)."""
    provider = SampleDataProvider()
    bars = await provider.bars("AAPL", datetime(2020, 1, 1), datetime(2022, 1, 1))
    spec = _make_spec()
    bt = BacktesterImpl()

    r1 = await bt.run(spec, bars)
    r2 = await bt.run(spec, bars)

    assert r1.n_trades == r2.n_trades
    assert r1.sharpe == r2.sharpe
    assert r1.net_edge == r2.net_edge
    assert r1.frictionless_edge == r2.frictionless_edge
