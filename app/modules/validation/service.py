from __future__ import annotations

import logging
from dataclasses import dataclass, field
from itertools import combinations
from pathlib import Path
from typing import Any, Protocol

import numpy as np
import yaml
from scipy import stats as scipy_stats

from app.core.dsl.schema import StrategySpec
from app.modules.backtest.service import BacktesterImpl, CostModel
import pandas as pd

logger = logging.getLogger(__name__)

GATES_VERSION = 2


def _load_validation_config() -> dict[str, Any]:
    path = Path(__file__).parents[3] / "config" / "validation.yaml"
    if path.exists():
        with open(path) as f:
            return yaml.safe_load(f) or {}
    return {}


@dataclass
class ValidationReport:
    deflated_sharpe: float
    pbo: float
    deg_slope: float
    peer_hit: float
    n_eff: int
    passed: bool
    confidence_curve: list[dict[str, Any]]
    gates_version: int = GATES_VERSION
    detail: dict[str, Any] = field(default_factory=dict)


class ValidationHarness(Protocol):
    async def validate(self, spec: dict, n_eff: int) -> ValidationReport: ...


class ValidationHarnessImpl:
    """Full validation gauntlet: walk-forward, DSR, PBO, robustness, confidence."""

    def __init__(
        self,
        dsr_threshold: float = 0.95,
        pbo_threshold: float = 0.20,
        min_trades: int = 100,
        cost_edge_ratio: float = 0.50,
        lockbox_pct: float = 0.15,
        peer_hit_threshold: float | None = None,
    ) -> None:
        self._dsr_threshold = dsr_threshold
        self._pbo_threshold = pbo_threshold
        self._min_trades = min_trades
        self._cost_edge_ratio = cost_edge_ratio
        self._lockbox_pct = lockbox_pct

        if peer_hit_threshold is not None:
            self._peer_hit_threshold = peer_hit_threshold
        else:
            config = _load_validation_config()
            thresholds = config.get("thresholds", {})
            self._peer_hit_threshold = thresholds.get("peer_hit_rate_min", 0.60)

    async def validate(
        self,
        spec: StrategySpec,
        bars: pd.DataFrame,
        n_eff: int = 1,
        n_splits: int = 5,
        peer_tickers: list[str] | None = None,
        provider=None,
        as_of=None,
    ) -> ValidationReport:
        bt = BacktesterImpl()
        result = await bt.run(spec, bars)

        # Compute returns series from equity curve
        equities = [e["equity"] for e in result.equity_curve]
        returns = np.diff(equities) / equities[:-1] if len(equities) > 1 else np.array([])

        # Walk-forward OOS returns
        oos_returns = self._walk_forward(returns, n_splits)

        # DSR
        sr_hat = self._sharpe_ratio(returns)
        n_obs = len(returns)
        skew = float(scipy_stats.skew(returns)) if len(returns) > 2 else 0.0
        kurt = float(scipy_stats.kurtosis(returns, fisher=False)) if len(returns) > 2 else 3.0
        sigma_sr = (
            np.std([self._sharpe_ratio(oos_returns[i]) for i in range(len(oos_returns))])
            if len(oos_returns) > 1
            else 1.0
        )
        dsr = self._deflated_sharpe(sr_hat, n_obs, skew, kurt, n_eff, sigma_sr)

        # PBO via CSCV
        pbo_result = self._pbo_cscv(returns, n_blocks=n_splits)
        pbo = pbo_result["pbo"]
        deg_slope = pbo_result["deg_slope"]

        # Confidence
        confidence_curve = self._compute_confidence(result, spec, n_eff)

        # Peer hit — backtest on correlated peers
        peer_hit_result = await self._compute_peer_hit(
            spec, peer_tickers, provider, as_of,
        )
        peer_hit = peer_hit_result["peer_hit"]
        peer_sufficient = peer_hit_result["sufficient"]

        # Gate checks
        gates = {
            "dsr": dsr >= self._dsr_threshold,
            "pbo": pbo <= self._pbo_threshold,
            "deg_slope": deg_slope >= 0,
            "min_trades": result.n_trades >= self._min_trades,
            "cost_edge": (
                result.net_edge >= self._cost_edge_ratio * result.frictionless_edge
                if result.frictionless_edge > 0
                else True
            ),
            "peer_hit": (
                peer_hit >= self._peer_hit_threshold
                if peer_sufficient
                else False
            ),
        }
        passed = all(gates.values())

        return ValidationReport(
            deflated_sharpe=round(dsr, 4),
            pbo=round(pbo, 4),
            deg_slope=round(deg_slope, 4),
            peer_hit=round(peer_hit, 4),
            n_eff=n_eff,
            passed=passed,
            confidence_curve=confidence_curve,
            gates_version=GATES_VERSION,
            detail={
                "gates": gates,
                "sharpe": round(float(sr_hat), 4),
                "skew": round(skew, 4),
                "kurtosis": round(kurt, 4),
                "n_trades": result.n_trades,
                "net_edge": result.net_edge,
                "frictionless_edge": result.frictionless_edge,
                "peer_hit_detail": peer_hit_result,
            },
        )

    async def validate_with_lockbox(
        self,
        spec: StrategySpec,
        bars: pd.DataFrame,
        n_eff: int = 1,
        n_splits: int = 5,
    ) -> ValidationReport:
        """Full validation with lockbox holdout.

        Splits bars into research portion (1-lockbox_pct) and lockbox (lockbox_pct).
        Runs the standard validation on the research portion first.
        If that passes, runs a final OOS check on the lockbox portion.
        If lockbox OOS performance degrades significantly, fails the validation.
        """
        n_total = len(bars)
        lockbox_start = int(n_total * (1 - self._lockbox_pct))

        research_bars = bars.iloc[:lockbox_start]
        lockbox_bars = bars.iloc[lockbox_start:]

        # Standard validation on research portion
        report = await self.validate(spec, research_bars, n_eff, n_splits)

        if not report.passed:
            report.detail["lockbox"] = "skipped — failed standard validation"
            return report

        # Lockbox OOS check
        bt = BacktesterImpl()
        lockbox_result = await bt.run(spec, lockbox_bars)
        lockbox_sharpe = self._sharpe_ratio(
            np.diff([e["equity"] for e in lockbox_result.equity_curve])
            / [e["equity"] for e in lockbox_result.equity_curve][:-1]
            if len(lockbox_result.equity_curve) > 1
            else np.array([])
        )

        # Lockbox must show non-negative Sharpe (not catastrophic degradation)
        lockbox_passed = lockbox_sharpe >= 0

        if not lockbox_passed:
            report.passed = False
            report.detail["lockbox"] = {
                "passed": False,
                "lockbox_sharpe": round(float(lockbox_sharpe), 4),
                "reason": "Strategy shows negative Sharpe on held-out lockbox data",
            }
        else:
            report.detail["lockbox"] = {
                "passed": True,
                "lockbox_sharpe": round(float(lockbox_sharpe), 4),
            }

        return report

    async def _compute_peer_hit(
        self,
        spec: StrategySpec,
        peer_tickers: list[str] | None,
        provider,
        as_of,
    ) -> dict:
        """Backtest spec on peers and return hit-rate dict.

        If peer_tickers or provider are None, fails closed with
        peer_hit=0.0 and sufficient=False.
        """
        if not peer_tickers or provider is None:
            return {
                "peer_hit": 0.0,
                "n_peers_tested": 0,
                "n_peers_with_edge": 0,
                "sufficient": False,
                "reason": "No peers or provider supplied",
                "details": [],
            }

        from datetime import datetime, timedelta
        from app.modules.data.peers import peer_backtest

        if as_of is None:
            as_of = datetime.now() - timedelta(days=1)

        return await peer_backtest(
            spec=spec,
            peer_tickers=peer_tickers,
            provider=provider,
            as_of=as_of,
        )

    def _sharpe_ratio(self, returns: np.ndarray) -> float:
        if len(returns) < 2 or np.std(returns) == 0:
            return 0.0
        return float(np.mean(returns) / np.std(returns))

    def _walk_forward(self, returns: np.ndarray, n_splits: int) -> list[np.ndarray]:
        if len(returns) < n_splits * 2:
            return [returns]
        fold_size = len(returns) // n_splits
        oos = []
        for i in range(1, n_splits):
            start = i * fold_size
            end = min(start + fold_size, len(returns))
            oos.append(returns[start:end])
        return oos

    @staticmethod
    def _psr(sr_hat: float, sr_benchmark: float, n: int, skew: float, kurt: float) -> float:
        if n < 2:
            return 0.0
        denom = np.sqrt(1 - skew * sr_hat + ((kurt - 1) / 4) * sr_hat**2)
        if denom <= 0:
            return 0.0
        z = (sr_hat - sr_benchmark) * np.sqrt(n - 1) / denom
        return float(scipy_stats.norm.cdf(z))

    @staticmethod
    def _expected_max_sharpe(n_eff: int, sigma_sr: float) -> float:
        if n_eff <= 1:
            return 0.0
        gamma = 0.5772156649  # Euler-Mascheroni
        e = np.e
        z1 = float(scipy_stats.norm.ppf(1 - 1 / n_eff)) if n_eff > 1 else 0.0
        z2 = float(scipy_stats.norm.ppf(1 - 1 / (n_eff * e))) if n_eff * e > 1 else 0.0
        return sigma_sr * ((1 - gamma) * z1 + gamma * z2)

    def _deflated_sharpe(
        self, sr_hat: float, n: int, skew: float, kurt: float, n_eff: int, sigma_sr: float
    ) -> float:
        sr_star = self._expected_max_sharpe(n_eff, sigma_sr)
        return self._psr(sr_hat, sr_star, n, skew, kurt)

    def _pbo_cscv(self, returns: np.ndarray, n_blocks: int = 6) -> dict[str, float]:
        """Probability of Backtest Overfitting via Combinatorial Symmetric Cross-Validation."""
        if n_blocks % 2 != 0:
            n_blocks = max(n_blocks - 1, 4)
        n = len(returns)
        if n < n_blocks * 10:
            return {"pbo": 0.5, "deg_slope": 0.0, "prob_loss": 0.5}

        block_size = n // n_blocks
        blocks = [returns[i * block_size : (i + 1) * block_size] for i in range(n_blocks)]

        half = n_blocks // 2
        combos = list(combinations(range(n_blocks), half))
        if len(combos) > 50:
            rng = np.random.default_rng(42)
            indices = rng.choice(len(combos), 50, replace=False)
            combos = [combos[i] for i in indices]

        logits = []
        is_perfs: list[float] = []
        oos_perfs: list[float] = []

        for is_idx in combos:
            oos_idx = tuple(b for b in range(n_blocks) if b not in is_idx)
            is_returns = np.concatenate([blocks[i] for i in is_idx])
            oos_returns = np.concatenate([blocks[i] for i in oos_idx])

            is_sharpe = self._sharpe_ratio(is_returns)
            oos_sharpe = self._sharpe_ratio(oos_returns)

            is_perfs.append(is_sharpe)
            oos_perfs.append(oos_sharpe)

            # For single-config: rank is binary (above or below median=0)
            r = 0.5 if oos_sharpe >= 0 else 0.25
            logit = np.log(r / (1 - r + 1e-10))
            logits.append(logit)

        pbo = sum(1 for x in logits if x <= 0) / max(len(logits), 1)

        # Degradation slope
        if len(is_perfs) > 1:
            slope, _, _, _, _ = scipy_stats.linregress(is_perfs, oos_perfs)
            deg_slope = float(slope)
        else:
            deg_slope = 0.0

        prob_loss = sum(1 for o in oos_perfs if o < 0) / max(len(oos_perfs), 1)

        return {"pbo": pbo, "deg_slope": deg_slope, "prob_loss": prob_loss}

    def _compute_confidence(
        self, backtest_result: Any, spec: StrategySpec, n_eff: int
    ) -> list[dict[str, Any]]:
        """Beta-Binomial confidence for each validation target."""
        targets = spec.validation.get("targets", [])
        curve: list[dict[str, Any]] = []
        trades = backtest_result.trades

        for target in targets:
            R = target.get("R", 0.02)
            H = target.get("H", 7)

            # Count successes: trades where net return >= R
            successes = 0
            total = 0
            for t in trades:
                if t.pnl_net != 0 and t.entry_price > 0:
                    ret = t.pnl_net / (t.shares * t.entry_price)
                    total += 1
                    if ret >= R:
                        successes += 1

            base_rate = 0.3
            s = min(2 + n_eff, 20)
            a0 = s * base_rate
            b0 = s * (1 - base_rate)
            a_post = a0 + successes
            b_post = b0 + total - successes

            from scipy.stats import beta as beta_dist

            c_mean = float(beta_dist.mean(a_post, b_post))
            c_lo = float(beta_dist.ppf(0.10, a_post, b_post))
            c_hi = float(beta_dist.ppf(0.90, a_post, b_post))

            curve.append(
                {
                    "target_R": R,
                    "horizon_H": H,
                    "C": round(c_mean, 4),
                    "C_lo": round(c_lo, 4),
                    "C_hi": round(c_hi, 4),
                    "successes": successes,
                    "total": total,
                }
            )

        return curve


def invalidate_stale_reports(reports: dict[str, dict]) -> int:
    """Mark in-memory validation reports that predate the peer-hit gate.

    Reports with gates_version < GATES_VERSION get passed=False and a
    stale_reason. Returns the count of invalidated reports.
    """
    count = 0
    for sid, report in reports.items():
        if report.get("gates_version", 0) < GATES_VERSION:
            report["passed"] = False
            report["stale_reason"] = (
                f"Report predates gates_version {GATES_VERSION} "
                "(peer_hit gate added); re-validate to clear."
            )
            count += 1
    if count:
        logger.info("Invalidated %d stale validation report(s)", count)
    return count
