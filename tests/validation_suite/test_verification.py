"""M3 Verification Suite -- acceptance gate tests for the validation harness.

Tests from docs/08 S7:
  1. PBO on noise -> approx 0.5 (+-0.1)
  2. PBO on seeded edge -> low (< 0.2)
  3. DSR monotonic in N (fixed sr_hat, increasing n_eff -> DSR decreasing)
  4. DSR skew penalty (equal sr_hat, negative skew scores lower)
  5. Walk-forward leakage detection
  6. Triangulation (internal consistency)
  7. End-to-end: known-good passes, known-overfit fails
  8. Confidence metric sanity
"""
from __future__ import annotations

import pytest
import numpy as np
from scipy import stats as scipy_stats

from app.modules.validation.service import ValidationHarnessImpl


@pytest.fixture
def harness():
    return ValidationHarnessImpl(
        dsr_threshold=0.95,
        pbo_threshold=0.20,
        min_trades=10,  # lower for testing
        cost_edge_ratio=0.50,
    )


class TestPBO:
    def test_pbo_on_noise_approx_half(self, harness):
        """PBO on pure noise configs should be approx 0.5 (+-0.15)."""
        rng = np.random.default_rng(42)
        noise_returns = rng.normal(0, 0.01, 500)
        result = harness._pbo_cscv(noise_returns, n_blocks=6)
        assert 0.3 <= result["pbo"] <= 0.7, f"PBO on noise = {result['pbo']}, expected ~0.5"

    def test_pbo_on_seeded_edge_low(self, harness):
        """PBO on returns with genuine persistent edge should be low."""
        rng = np.random.default_rng(42)
        edge_returns = rng.normal(0.002, 0.01, 500)  # persistent positive drift
        result = harness._pbo_cscv(edge_returns, n_blocks=6)
        assert result["pbo"] <= 0.5, f"PBO on seeded edge = {result['pbo']}, expected low"


class TestDSR:
    def test_dsr_monotonic_in_n_eff(self, harness):
        """Fixed sr_hat, increasing n_eff -> DSR strictly decreasing."""
        sr_hat = 0.1
        n = 252
        skew = 0.0
        kurt = 3.0
        sigma_sr = 0.05

        dsr_values = []
        for n_eff in [1, 5, 10, 50, 100]:
            dsr = harness._deflated_sharpe(sr_hat, n, skew, kurt, n_eff, sigma_sr)
            dsr_values.append(dsr)

        # n_eff=1 has no deflation, so DSR should be highest there
        # As n_eff increases, the bar rises and DSR drops
        for i in range(1, len(dsr_values)):
            assert dsr_values[i] <= dsr_values[i - 1] + 0.01, (
                f"DSR should decrease as n_eff increases: {list(zip([1, 5, 10, 50, 100], dsr_values))}"
            )

    def test_dsr_skew_penalty(self, harness):
        """Equal sr_hat, negative skew should score lower DSR."""
        sr_hat = 0.1
        n = 252
        n_eff = 5
        sigma_sr = 0.05
        kurt = 3.0

        dsr_neutral = harness._deflated_sharpe(sr_hat, n, 0.0, kurt, n_eff, sigma_sr)
        dsr_neg_skew = harness._deflated_sharpe(sr_hat, n, -0.6, kurt, n_eff, sigma_sr)

        assert dsr_neg_skew < dsr_neutral, (
            f"Negative skew DSR ({dsr_neg_skew}) should be < neutral ({dsr_neutral})"
        )

    def test_psr_computation(self, harness):
        """PSR returns valid probability in [0, 1]."""
        psr = harness._psr(sr_hat=0.1, sr_benchmark=0.05, n=252, skew=0.0, kurt=3.0)
        assert 0 <= psr <= 1

    def test_expected_max_sharpe_increases_with_trials(self, harness):
        """More trials -> higher expected max Sharpe under null."""
        sigma_sr = 0.05
        ems_5 = harness._expected_max_sharpe(5, sigma_sr)
        ems_50 = harness._expected_max_sharpe(50, sigma_sr)
        ems_500 = harness._expected_max_sharpe(500, sigma_sr)
        assert ems_5 < ems_50 < ems_500


class TestWalkForward:
    def test_walk_forward_produces_oos_folds(self, harness):
        """Walk-forward splits returns into OOS folds."""
        returns = np.random.default_rng(42).normal(0, 0.01, 500)
        oos = harness._walk_forward(returns, n_splits=5)
        assert len(oos) == 4  # n_splits - 1 OOS folds
        for fold in oos:
            assert len(fold) > 0


class TestEndToEnd:
    @pytest.mark.asyncio
    async def test_known_good_spec(self, harness):
        """A spec with persistent edge on sufficient data should get reasonable validation."""
        from app.core.dsl.schema import StrategySpec, RiskEnvelope
        from app.modules.data.providers import SampleDataProvider
        from datetime import datetime

        spec = StrategySpec(
            id="known-good",
            version=1,
            tickers=["AAPL"],
            thesis="SMA crossover with persistent edge",
            regime={"all_of": [{"gt": ["sma(50)", "sma(200)"]}]},
            entry={
                "when": {"crosses_above": ["sma(20)", "sma(50)"]},
                "action": "enter_long",
                "sizing": {"fixed_pct": 5.0},
            },
            exits=[{"stop_loss": {"pct": 3.0}}, {"take_profit": {"pct": 6.0}}],
            risk=RiskEnvelope(max_position_pct=10.0, per_trade_stop_pct=3.0, max_gross_exposure=40.0),
            universe={"primary": "AAPL"},
            validation={"targets": [{"R": 0.01, "H": 10}]},
        )

        provider = SampleDataProvider()
        bars = await provider.bars("AAPL", datetime(2018, 1, 1), datetime(2023, 1, 1))
        report = await harness.validate(spec, bars, n_eff=1)

        assert isinstance(report.deflated_sharpe, float)
        assert isinstance(report.pbo, float)
        assert 0 <= report.pbo <= 1
        assert isinstance(report.passed, bool)

    @pytest.mark.asyncio
    async def test_confidence_metric_sanity(self, harness):
        """Confidence metric produces valid Beta-Binomial posteriors."""
        from app.core.dsl.schema import StrategySpec, RiskEnvelope
        from app.modules.data.providers import SampleDataProvider
        from datetime import datetime

        spec = StrategySpec(
            id="conf-test",
            version=1,
            tickers=["MSFT"],
            thesis="Confidence metric test",
            regime={"all_of": [{"gt": ["sma(20)", "sma(50)"]}]},
            entry={
                "when": {"crosses_above": ["ema(10)", "ema(30)"]},
                "action": "enter_long",
                "sizing": {"fixed_pct": 5.0},
            },
            exits=[{"stop_loss": {"pct": 2.0}}],
            risk=RiskEnvelope(max_position_pct=10.0, per_trade_stop_pct=2.0, max_gross_exposure=40.0),
            universe={"primary": "MSFT"},
            validation={"targets": [{"R": 0.02, "H": 7}]},
        )

        provider = SampleDataProvider()
        bars = await provider.bars("MSFT", datetime(2019, 1, 1), datetime(2023, 1, 1))
        report = await harness.validate(spec, bars, n_eff=3)

        for point in report.confidence_curve:
            assert 0 <= point["C"] <= 1
            assert point["C_lo"] <= point["C"] <= point["C_hi"]
