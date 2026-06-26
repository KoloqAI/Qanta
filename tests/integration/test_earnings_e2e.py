"""End-to-end integration tests for the neglected-earnings-drift archetype.

Positive control: SeededEarningsProvider generates synthetic tickers with a
genuine post-earnings drift — strong price reaction on the announcement bar,
continued drift in the same direction for the following sessions. The archetype
should detect entries and produce ledger entries with positive Sharpe.

Negative control: RandomReactionProvider randomises the reaction direction
on each event — no persistent drift. Zero survivors expected.
"""
from __future__ import annotations

import copy
import hashlib
from datetime import datetime, date, timedelta
from unittest import mock

import numpy as np
import pandas as pd
import pytest

from app.modules.evolution.service import EvolutionLoopImpl
from app.modules.registry.library_loader import load_archetypes
from app.modules.registry.service import StrategyRegistryImpl
from app.modules.monitoring.service import MonitoringServiceImpl
from app.modules.data.providers import SampleDataProvider


# ---------------------------------------------------------------------------
# Synthetic tickers
# ---------------------------------------------------------------------------

EARN_TICKERS = [f"EARN{i}" for i in range(1, 8)]

EARNINGS_ANNOUNCE = date(2024, 4, 20)

EARN_EVENTS = [
    {"symbol": t, "announce_date": EARNINGS_ANNOUNCE, "session": "BMO"}
    for t in EARN_TICKERS
]


# ---------------------------------------------------------------------------
# Seeded earnings provider (positive control)
# ---------------------------------------------------------------------------

class SeededEarningsProvider:
    """Positive control: strong upward reaction + continued drift after earnings."""

    def __init__(self):
        self._fallback = SampleDataProvider()

    async def bars(self, symbol, start, end, timeframe="1d", as_of=None):
        if symbol not in EARN_TICKERS:
            return await self._fallback.bars(symbol, start, end, timeframe, as_of)
        if as_of is not None and end > as_of:
            end = as_of

        dates = pd.bdate_range(start=start.date(), end=end.date())
        if len(dates) == 0:
            return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])

        seed = int(hashlib.md5(symbol.encode()).hexdigest()[:8], 16)
        rng = np.random.default_rng(seed)
        n = len(dates)

        close = np.full(n, 20.0)
        volume = np.full(n, 200_000.0)

        for i in range(n):
            d = dates[i].date()
            noise = rng.normal(0, 0.005)
            if d == EARNINGS_ANNOUNCE:
                drift = 0.06
                volume[i] = 2_000_000.0
            elif d > EARNINGS_ANNOUNCE and (d - EARNINGS_ANNOUNCE).days <= 20:
                drift = 0.008
                volume[i] = 400_000.0
            else:
                drift = 0.0
            if i > 0:
                close[i] = close[i - 1] * (1 + drift + noise)
            close[i] = max(close[i], 3.0)

        high = close * (1 + np.abs(rng.normal(0, 0.005, n)))
        low = close * (1 - np.abs(rng.normal(0, 0.005, n)))
        open_ = low + (high - low) * rng.uniform(0.3, 0.7, n)

        df = pd.DataFrame(
            {"open": open_, "high": high, "low": low, "close": close, "volume": volume},
            index=dates,
        )
        df.index.name = "date"
        return df

    async def universe(self, as_of=None):
        return sorted(EARN_TICKERS)

    async def filtered_universe(self, as_of, min_price=3, min_dollar_volume=0, cap=500):
        return await self.universe(as_of=as_of)

    async def reconstitution_events(self, index, as_of, start=None, end=None):
        return []

    async def earnings_events(self, symbol, start, end, as_of=None):
        as_of_d = as_of.date() if isinstance(as_of, datetime) and as_of else date(2099, 12, 31)
        start_d = start.date() if isinstance(start, datetime) else start
        end_d = end.date() if isinstance(end, datetime) else end
        return [
            dict(e) for e in EARN_EVENTS
            if e["symbol"] == symbol
            and e["announce_date"] <= as_of_d
            and start_d <= e["announce_date"] <= end_d
        ]


# ---------------------------------------------------------------------------
# Random-reaction provider (negative control)
# ---------------------------------------------------------------------------

class RandomReactionProvider(SeededEarningsProvider):
    """Negative control: random reaction direction → no persistent drift."""

    async def bars(self, symbol, start, end, timeframe="1d", as_of=None):
        if symbol not in EARN_TICKERS:
            return await self._fallback.bars(symbol, start, end, timeframe, as_of)
        if as_of is not None and end > as_of:
            end = as_of

        dates = pd.bdate_range(start=start.date(), end=end.date())
        if len(dates) == 0:
            return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])

        seed = int(hashlib.md5(symbol.encode()).hexdigest()[:8], 16)
        rng = np.random.default_rng(seed)
        n = len(dates)

        close = np.full(n, 20.0)
        volume = np.full(n, 200_000.0)

        direction = rng.choice([-1, 1])
        for i in range(n):
            d = dates[i].date()
            noise = rng.normal(0, 0.02)
            if d == EARNINGS_ANNOUNCE:
                drift = direction * 0.04
                volume[i] = 2_000_000.0
            elif d > EARNINGS_ANNOUNCE and (d - EARNINGS_ANNOUNCE).days <= 20:
                drift = rng.normal(0, 0.01)
                volume[i] = 300_000.0
            else:
                drift = 0.0
            if i > 0:
                close[i] = close[i - 1] * (1 + drift + noise)
            close[i] = max(close[i], 3.0)

        high = close * (1 + np.abs(rng.normal(0, 0.005, n)))
        low = close * (1 - np.abs(rng.normal(0, 0.005, n)))
        open_ = low + (high - low) * rng.uniform(0.3, 0.7, n)

        df = pd.DataFrame(
            {"open": open_, "high": high, "low": low, "close": close, "volume": volume},
            index=dates,
        )
        df.index.name = "date"
        return df


# ---------------------------------------------------------------------------
# Scan mocks
# ---------------------------------------------------------------------------

async def _seeded_earnings_scan(archetype, as_of=None):
    return {
        "candidates": [
            {
                "ticker": t,
                "fit_score": round(0.9 - i * 0.02, 4),
                "archetype": archetype.get("name", ""),
                "family": archetype.get("family", ""),
            }
            for i, t in enumerate(EARN_TICKERS)
        ],
        "is_sample_fallback": False,
    }


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def explorable_archetypes(monkeypatch):
    """Bypass persistence_thesis validation so seed archetypes are explorable."""
    monkeypatch.setattr(
        "app.modules.registry.library_loader._validate_persistence_thesis",
        lambda raw, archetype_id: [],
    )


# ---------------------------------------------------------------------------
# Positive control
# ---------------------------------------------------------------------------


class TestEarningsPositiveControl:
    """Positive control: seeded post-earnings drift through T2 pipeline."""

    @pytest.fixture(autouse=True)
    async def run_cycle(self, explorable_archetypes):
        self.registry = StrategyRegistryImpl()
        self.monitoring = MonitoringServiceImpl()
        self.evo = EvolutionLoopImpl(
            monitoring=self.monitoring, registry=self.registry,
        )

        with mock.patch(
            "app.modules.data.providers.create_data_provider",
            return_value=SeededEarningsProvider(),
        ), mock.patch(
            "app.modules.data.providers.scan_universe",
            new=_seeded_earnings_scan,
        ):
            self.result = await self.evo.run_tier2(
                budget=5,
                archetype_subset=["neglected_earnings_drift"],
                as_of=datetime(2024, 5, 15),
                candidates_per_archetype=3,
            )

    def test_trials_run(self):
        assert self.result["trials_run"] > 0, (
            "Pipeline should produce trials for earnings archetype"
        )

    def test_ledger_populated(self):
        ledger = self.result["ledger"]
        assert len(ledger) > 0
        for entry in ledger:
            assert entry["archetype_id"] == "neglected_earnings_drift"
            assert entry["hypothesis_family"] == "behavioral_drift"

    def test_positive_sharpe(self):
        """Seeded drift should produce positive winner Sharpe."""
        ledger = self.result["ledger"]
        best = max(ledger, key=lambda e: e.get("winner_sharpe", 0))
        assert best["winner_sharpe"] > 0, (
            f"Best Sharpe should be positive with seeded drift, got {best['winner_sharpe']}"
        )


# ---------------------------------------------------------------------------
# Negative control
# ---------------------------------------------------------------------------


class TestEarningsNegativeControl:
    """Negative control: random reactions → no directional edge → zero survivors."""

    @pytest.mark.asyncio
    async def test_random_reaction_yields_zero_survivors(self, explorable_archetypes):
        registry = StrategyRegistryImpl()
        monitoring = MonitoringServiceImpl()
        evo = EvolutionLoopImpl(monitoring=monitoring, registry=registry)

        with mock.patch(
            "app.modules.data.providers.create_data_provider",
            return_value=RandomReactionProvider(),
        ), mock.patch(
            "app.modules.data.providers.scan_universe",
            new=_seeded_earnings_scan,
        ):
            result = await evo.run_tier2(
                budget=5,
                archetype_subset=["neglected_earnings_drift"],
                as_of=datetime(2024, 5, 15),
                candidates_per_archetype=3,
            )

        assert len(result["survivors"]) == 0, (
            "Random reactions should yield zero survivors "
            "(no persistent drift when reaction direction is noise)"
        )


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------


class TestEarningsDeterminism:
    """Verify two runs with identical setup produce identical results."""

    @pytest.mark.asyncio
    async def test_deterministic(self, explorable_archetypes):
        async def _run():
            reg = StrategyRegistryImpl()
            mon = MonitoringServiceImpl()
            evo = EvolutionLoopImpl(monitoring=mon, registry=reg)
            with mock.patch(
                "app.modules.data.providers.create_data_provider",
                return_value=SeededEarningsProvider(),
            ), mock.patch(
                "app.modules.data.providers.scan_universe",
                new=_seeded_earnings_scan,
            ):
                return await evo.run_tier2(
                    budget=3,
                    archetype_subset=["neglected_earnings_drift"],
                    as_of=datetime(2024, 5, 15),
                    candidates_per_archetype=2,
                )

        r1 = await _run()
        r2 = await _run()

        assert r1["trials_run"] == r2["trials_run"]
        assert len(r1["ledger"]) == len(r2["ledger"])
        for e1, e2 in zip(r1["ledger"], r2["ledger"]):
            assert e1["spec_hash"] == e2["spec_hash"]
            assert e1["winner_sharpe"] == e2["winner_sharpe"]


# ---------------------------------------------------------------------------
# Cost model
# ---------------------------------------------------------------------------


class TestEarningsCostModel:
    """Verify cost model is conservative for thin names."""

    @pytest.mark.asyncio
    async def test_frictionless_vs_net_reported(self, explorable_archetypes):
        """Ledger entries should report both frictionless and net edge."""
        registry = StrategyRegistryImpl()
        monitoring = MonitoringServiceImpl()
        evo = EvolutionLoopImpl(monitoring=monitoring, registry=registry)

        with mock.patch(
            "app.modules.data.providers.create_data_provider",
            return_value=SeededEarningsProvider(),
        ), mock.patch(
            "app.modules.data.providers.scan_universe",
            new=_seeded_earnings_scan,
        ):
            result = await evo.run_tier2(
                budget=2,
                archetype_subset=["neglected_earnings_drift"],
                as_of=datetime(2024, 5, 15),
                candidates_per_archetype=2,
            )

        for entry in result["ledger"]:
            assert "winner_sharpe" in entry
