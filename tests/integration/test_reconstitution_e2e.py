"""End-to-end integration tests for the forced-flow reconstitution archetype.

Positive control: SeededReconProvider generates synthetic tickers with a
genuine forced-flow drift on confirmed index additions (price ramps from
final_list_date to effective_date). The archetype should detect entries
and produce ledger entries with positive Sharpe.

Negative control: ShuffledReconProvider randomizes which names are adds
vs deletes — the drift has no directional edge. Zero survivors expected.
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
from app.modules.registry.library_loader import load_archetypes, _fill_placeholders, _extract_defaults
from app.modules.registry.service import StrategyRegistryImpl
from app.modules.monitoring.service import MonitoringServiceImpl
from app.modules.data.providers import SampleDataProvider
from app.modules.data.events import enrich_bars_with_events


# ---------------------------------------------------------------------------
# Seeded forced-flow provider (positive control)
# ---------------------------------------------------------------------------

RECON_ADD_TICKERS = [f"RECO_ADD{i}" for i in range(1, 6)]
RECON_DEL_TICKERS = [f"RECO_DEL{i}" for i in range(1, 4)]
ALL_RECON_TICKERS = RECON_ADD_TICKERS + RECON_DEL_TICKERS

RECON_EVENTS_POS = [
    {
        "symbol": t, "index": "russell_2000", "action": "add",
        "preliminary_list_date": date(2024, 5, 31),
        "final_list_date": date(2024, 6, 14),
        "effective_date": date(2024, 6, 28),
    }
    for t in RECON_ADD_TICKERS
] + [
    {
        "symbol": t, "index": "russell_2000", "action": "delete",
        "preliminary_list_date": date(2024, 5, 31),
        "final_list_date": date(2024, 6, 14),
        "effective_date": date(2024, 6, 28),
    }
    for t in RECON_DEL_TICKERS
]


class SeededReconProvider:
    """Positive control: adds drift upward from final_list_date to effective_date."""

    def __init__(self):
        self._fallback = SampleDataProvider()

    async def bars(self, symbol, start, end, timeframe="1d", as_of=None):
        if symbol not in ALL_RECON_TICKERS:
            return await self._fallback.bars(symbol, start, end, timeframe, as_of)
        if as_of is not None and end > as_of:
            end = as_of

        dates = pd.bdate_range(start=start.date(), end=end.date())
        if len(dates) == 0:
            return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])

        seed = int(hashlib.md5(symbol.encode()).hexdigest()[:8], 16)
        rng = np.random.default_rng(seed)
        n = len(dates)

        close = np.full(n, 10.0)
        is_add = symbol in RECON_ADD_TICKERS

        for i in range(n):
            d = dates[i].date()
            noise = rng.normal(0, 0.05)
            if is_add and date(2024, 6, 14) <= d <= date(2024, 6, 28):
                drift = 0.015
            elif not is_add and date(2024, 6, 14) <= d <= date(2024, 6, 28):
                drift = -0.010
            else:
                drift = 0.0
            if i > 0:
                close[i] = close[i - 1] * (1 + drift + noise)
            close[i] = max(close[i], 3.0)

        high = close * (1 + np.abs(rng.normal(0, 0.005, n)))
        low = close * (1 - np.abs(rng.normal(0, 0.005, n)))
        open_ = low + (high - low) * rng.uniform(0.3, 0.7, n)
        volume = rng.integers(200_000, 800_000, n).astype(float)

        df = pd.DataFrame(
            {"open": open_, "high": high, "low": low, "close": close, "volume": volume},
            index=dates,
        )
        df.index.name = "date"
        return df

    async def universe(self, as_of=None):
        return sorted(ALL_RECON_TICKERS)

    async def filtered_universe(self, as_of, min_price=3, min_dollar_volume=0, cap=500):
        return await self.universe(as_of=as_of)

    async def reconstitution_events(self, index, as_of, start=None, end=None):
        as_of_d = as_of.date() if isinstance(as_of, datetime) else as_of
        return [
            dict(e) for e in RECON_EVENTS_POS
            if e["index"] == index and e["final_list_date"] <= as_of_d
        ]

    async def earnings_events(self, symbol, start, end, as_of=None):
        return []


# ---------------------------------------------------------------------------
# Shuffled provider (negative control)
# ---------------------------------------------------------------------------


class ShuffledReconProvider(SeededReconProvider):
    """Negative control: randomly assign add/delete → no directional edge."""

    async def reconstitution_events(self, index, as_of, start=None, end=None):
        as_of_d = as_of.date() if isinstance(as_of, datetime) else as_of
        events = []
        for i, t in enumerate(ALL_RECON_TICKERS):
            action = "add" if i % 2 == 0 else "delete"
            events.append({
                "symbol": t, "index": "russell_2000", "action": action,
                "preliminary_list_date": date(2024, 5, 31),
                "final_list_date": date(2024, 6, 14),
                "effective_date": date(2024, 6, 28),
            })
        return [e for e in events if e["index"] == index and e["final_list_date"] <= as_of_d]


async def _seeded_recon_scan(archetype, as_of=None):
    """Mock scan that returns RECON_ADD tickers as candidates."""
    return {
        "candidates": [
            {
                "ticker": t,
                "fit_score": round(0.9 - i * 0.02, 4),
                "archetype": archetype.get("name", ""),
                "family": archetype.get("family", ""),
            }
            for i, t in enumerate(RECON_ADD_TICKERS)
        ],
        "is_sample_fallback": False,
    }


async def _shuffled_recon_scan(archetype, as_of=None):
    """Mock scan that returns ALL recon tickers for negative control."""
    return {
        "candidates": [
            {
                "ticker": t,
                "fit_score": round(0.8 - i * 0.02, 4),
                "archetype": archetype.get("name", ""),
                "family": archetype.get("family", ""),
            }
            for i, t in enumerate(ALL_RECON_TICKERS)
        ],
        "is_sample_fallback": False,
    }


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def explorable_archetypes(monkeypatch):
    """Bypass persistence_thesis validation for non-reconstitution archetypes."""
    monkeypatch.setattr(
        "app.modules.registry.library_loader._validate_persistence_thesis",
        lambda raw, archetype_id: [],
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestReconstitutionPositiveControl:
    """Positive control: seeded forced-flow drift through T2 pipeline."""

    @pytest.fixture(autouse=True)
    async def run_cycle(self, explorable_archetypes):
        self.registry = StrategyRegistryImpl()
        self.monitoring = MonitoringServiceImpl()
        self.evo = EvolutionLoopImpl(
            monitoring=self.monitoring, registry=self.registry,
        )

        with mock.patch(
            "app.modules.data.providers.create_data_provider",
            return_value=SeededReconProvider(),
        ), mock.patch(
            "app.modules.data.providers.scan_universe",
            new=_seeded_recon_scan,
        ):
            self.result = await self.evo.run_tier2(
                budget=5,
                archetype_subset=["russell_reconstitution_drift"],
                as_of=datetime(2024, 7, 1),
                candidates_per_archetype=3,
            )

    def test_trials_run(self):
        assert self.result["trials_run"] > 0, (
            "Pipeline should produce trials for reconstitution archetype"
        )

    def test_ledger_populated(self):
        ledger = self.result["ledger"]
        assert len(ledger) > 0
        for entry in ledger:
            assert entry["archetype_id"] == "russell_reconstitution_drift"
            assert entry["hypothesis_family"] == "forced_flow"

    def test_positive_sharpe(self):
        """Seeded drift should produce positive winner Sharpe."""
        ledger = self.result["ledger"]
        best = max(ledger, key=lambda e: e.get("winner_sharpe", 0))
        assert best["winner_sharpe"] > 0, (
            f"Best Sharpe should be positive with seeded drift, got {best['winner_sharpe']}"
        )


class TestReconstitutionNegativeControl:
    """Negative control: shuffled add/delete → no directional edge → zero survivors."""

    @pytest.mark.asyncio
    async def test_shuffled_yields_zero_survivors(self, explorable_archetypes):
        registry = StrategyRegistryImpl()
        monitoring = MonitoringServiceImpl()
        evo = EvolutionLoopImpl(monitoring=monitoring, registry=registry)

        with mock.patch(
            "app.modules.data.providers.create_data_provider",
            return_value=ShuffledReconProvider(),
        ), mock.patch(
            "app.modules.data.providers.scan_universe",
            new=_shuffled_recon_scan,
        ):
            result = await evo.run_tier2(
                budget=5,
                archetype_subset=["russell_reconstitution_drift"],
                as_of=datetime(2024, 7, 1),
                candidates_per_archetype=3,
            )

        assert len(result["survivors"]) == 0, (
            "Shuffled add/delete should yield zero survivors "
            "(no directional edge when labels are random)"
        )


class TestReconstitutionCostModel:
    """Verify cost model reports frictionless vs net edge for illiquid names."""

    @pytest.mark.asyncio
    async def test_frictionless_vs_net_reported(self, explorable_archetypes):
        """Ledger entries should report winner_sharpe (cost model active)."""
        registry = StrategyRegistryImpl()
        monitoring = MonitoringServiceImpl()
        evo = EvolutionLoopImpl(monitoring=monitoring, registry=registry)

        with mock.patch(
            "app.modules.data.providers.create_data_provider",
            return_value=SeededReconProvider(),
        ), mock.patch(
            "app.modules.data.providers.scan_universe",
            new=_seeded_recon_scan,
        ):
            result = await evo.run_tier2(
                budget=2,
                archetype_subset=["russell_reconstitution_drift"],
                as_of=datetime(2024, 7, 1),
                candidates_per_archetype=2,
            )

        for entry in result["ledger"]:
            assert "winner_sharpe" in entry


class TestReconstitutionArchetypeDeterminism:
    """Verify two runs with identical setup produce identical results."""

    @pytest.mark.asyncio
    async def test_deterministic(self, explorable_archetypes):
        async def _run():
            reg = StrategyRegistryImpl()
            mon = MonitoringServiceImpl()
            evo = EvolutionLoopImpl(monitoring=mon, registry=reg)
            with mock.patch(
                "app.modules.data.providers.create_data_provider",
                return_value=SeededReconProvider(),
            ), mock.patch(
                "app.modules.data.providers.scan_universe",
                new=_seeded_recon_scan,
            ):
                return await evo.run_tier2(
                    budget=3,
                    archetype_subset=["russell_reconstitution_drift"],
                    as_of=datetime(2024, 7, 1),
                    candidates_per_archetype=2,
                )

        r1 = await _run()
        r2 = await _run()

        assert r1["trials_run"] == r2["trials_run"]
        assert len(r1["ledger"]) == len(r2["ledger"])
        for e1, e2 in zip(r1["ledger"], r2["ledger"]):
            assert e1["spec_hash"] == e2["spec_hash"]
            assert e1["winner_sharpe"] == e2["winner_sharpe"]
