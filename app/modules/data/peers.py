"""Correlation-based peer selection for peer-hit validation.

Peers = the N names most return-correlated to the primary over a lookback,
computed POINT-IN-TIME (as_of clamped, no future data).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

MIN_OVERLAP_DAYS = 60


@dataclass
class PeerSelectionResult:
    peers: list[str]
    primary: str
    sufficient: bool
    reason: str


async def select_correlation_peers(
    primary: str,
    candidates: list[str],
    provider,
    as_of: datetime,
    n_peers: int = 10,
    min_peers: int = 5,
    lookback_days: int = 252,
) -> PeerSelectionResult:
    """Select the N most return-correlated tickers to *primary*.

    Point-in-time: bars are clamped to *as_of*.
    If fewer than *min_peers* have sufficient overlapping data,
    returns sufficient=False (caller should fail closed).
    """
    start = as_of - timedelta(days=int(lookback_days * 1.5))

    primary_bars = await provider.bars(primary, start, as_of, as_of=as_of)
    if primary_bars.empty or len(primary_bars) < MIN_OVERLAP_DAYS:
        return PeerSelectionResult(
            peers=[],
            primary=primary,
            sufficient=False,
            reason=f"Primary {primary} has insufficient data ({len(primary_bars)} bars, need {MIN_OVERLAP_DAYS})",
        )

    primary_returns = np.log(primary_bars["close"] / primary_bars["close"].shift(1)).dropna()

    correlations: list[tuple[str, float]] = []

    for ticker in candidates:
        if ticker == primary:
            continue
        try:
            bars = await provider.bars(ticker, start, as_of, as_of=as_of)
        except Exception:
            logger.debug("Failed to fetch bars for peer candidate %s", ticker)
            continue
        if bars.empty or len(bars) < MIN_OVERLAP_DAYS:
            continue

        peer_returns = np.log(bars["close"] / bars["close"].shift(1)).dropna()

        aligned = pd.concat(
            [primary_returns.rename("primary"), peer_returns.rename("peer")],
            axis=1,
            join="inner",
        ).dropna()

        if len(aligned) < MIN_OVERLAP_DAYS:
            continue

        corr = float(aligned["primary"].corr(aligned["peer"]))
        if np.isnan(corr):
            continue
        correlations.append((ticker, corr))

    correlations.sort(key=lambda x: x[1], reverse=True)
    selected = [t for t, _ in correlations[:n_peers]]

    if len(selected) < min_peers:
        return PeerSelectionResult(
            peers=selected,
            primary=primary,
            sufficient=False,
            reason=(
                f"Only {len(selected)} correlated peers found "
                f"(need {min_peers}); {len(candidates)} candidates screened"
            ),
        )

    return PeerSelectionResult(
        peers=selected,
        primary=primary,
        sufficient=True,
        reason=f"{len(selected)} peers selected from {len(candidates)} candidates",
    )


async def peer_backtest(
    spec,
    peer_tickers: list[str],
    provider,
    as_of: datetime,
    lookback_days: int = 700,
    edge_threshold: float = 0.0,
) -> dict:
    """Backtest *spec* on each peer ticker and compute peer-hit rate.

    peer_hit = fraction of peers where net_edge > edge_threshold.
    Returns dict with peer_hit, per-peer results, and whether sufficient.
    """
    from app.core.dsl.schema import StrategySpec
    from app.modules.backtest.service import BacktesterImpl

    start = as_of - timedelta(days=lookback_days)
    bt = BacktesterImpl()
    results: list[dict] = []

    for ticker in peer_tickers:
        try:
            bars = await provider.bars(ticker, start, as_of, as_of=as_of)
        except Exception:
            logger.warning("Failed to fetch bars for peer %s", ticker)
            results.append({"ticker": ticker, "error": "no_data", "has_edge": False})
            continue

        if bars.empty or len(bars) < 50:
            results.append({"ticker": ticker, "error": "insufficient_bars", "has_edge": False})
            continue

        peer_spec = StrategySpec(
            id=spec.id,
            version=spec.version,
            tickers=[ticker],
            thesis=spec.thesis,
            regime=spec.regime,
            entry=spec.entry,
            exits=spec.exits,
            risk=spec.risk,
            universe=spec.universe,
            validation=spec.validation,
        )

        try:
            bt_result = await bt.run(peer_spec, bars)
        except Exception:
            logger.warning("Backtest failed for peer %s", ticker, exc_info=True)
            results.append({"ticker": ticker, "error": "backtest_failed", "has_edge": False})
            continue

        has_edge = bt_result.net_edge > edge_threshold
        results.append({
            "ticker": ticker,
            "net_edge": round(bt_result.net_edge, 4),
            "sharpe": round(bt_result.sharpe, 4),
            "n_trades": bt_result.n_trades,
            "has_edge": has_edge,
        })

    valid_results = [r for r in results if "error" not in r]
    if not valid_results:
        return {
            "peer_hit": 0.0,
            "n_peers_tested": 0,
            "n_peers_with_edge": 0,
            "sufficient": False,
            "reason": "No peers produced valid backtest results",
            "details": results,
        }

    hits = sum(1 for r in valid_results if r["has_edge"])
    peer_hit = hits / len(valid_results)

    return {
        "peer_hit": round(peer_hit, 4),
        "n_peers_tested": len(valid_results),
        "n_peers_with_edge": hits,
        "sufficient": True,
        "reason": f"{hits}/{len(valid_results)} peers show edge",
        "details": results,
    }
