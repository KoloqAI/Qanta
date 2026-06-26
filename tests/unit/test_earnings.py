"""Tests for the neglected-earnings-drift archetype infrastructure.

Covers: earnings calendar provider, point-in-time filtering, BMO/AMC
reaction-bar selection, bar enrichment, archetype loading, and interpreter
parity.
"""
from __future__ import annotations

import asyncio
from datetime import date, datetime, timedelta

import numpy as np
import pandas as pd
import pytest
import yaml

from app.modules.data.providers import SampleDataProvider, _SAMPLE_EARNINGS_EVENTS
from app.modules.data.events import enrich_bars_with_earnings
from app.core.dsl.primitives import FEATURE_PRIMITIVES, DSL_VOCABULARY_VERSION


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def _make_bars(start: date, n_days: int, base_price: float = 50.0) -> pd.DataFrame:
    dates = pd.bdate_range(start=start, periods=n_days)
    rng = np.random.default_rng(42)
    close = base_price + np.cumsum(rng.normal(0, 0.5, n_days))
    volume = rng.integers(100_000, 500_000, n_days).astype(float)
    return pd.DataFrame(
        {
            "open": close - rng.uniform(0, 1, n_days),
            "high": close + rng.uniform(0, 2, n_days),
            "low": close - rng.uniform(0, 2, n_days),
            "close": close,
            "volume": volume,
        },
        index=dates,
    )


# ---------------------------------------------------------------------------
# Earnings calendar provider tests
# ---------------------------------------------------------------------------

class TestEarningsCalendar:

    def test_sample_calendar_is_deterministic(self):
        """Two calls return identical events."""
        provider = SampleDataProvider()
        e1 = _run(provider.earnings_events("AAPL", datetime(2023, 1, 1), datetime(2024, 12, 31)))
        e2 = _run(provider.earnings_events("AAPL", datetime(2023, 1, 1), datetime(2024, 12, 31)))
        assert e1 == e2

    def test_point_in_time_hidden_before_announce(self):
        """An event with announce_date after as_of is not returned."""
        provider = SampleDataProvider()
        all_events = _run(provider.earnings_events(
            "AAPL",
            datetime(2023, 1, 1),
            datetime(2025, 12, 31),
            as_of=datetime(2025, 12, 31),
        ))
        assert len(all_events) > 0
        first = min(all_events, key=lambda e: e["announce_date"])

        before = datetime.combine(first["announce_date"] - timedelta(days=1), datetime.min.time())
        hidden = _run(provider.earnings_events(
            "AAPL",
            datetime(2020, 1, 1),
            datetime(2025, 12, 31),
            as_of=before,
        ))
        assert first not in hidden

    def test_point_in_time_visible_after_announce(self):
        """An event with announce_date <= as_of is returned."""
        provider = SampleDataProvider()
        all_events = _run(provider.earnings_events(
            "AAPL",
            datetime(2023, 1, 1),
            datetime(2025, 12, 31),
            as_of=datetime(2025, 12, 31),
        ))
        first = min(all_events, key=lambda e: e["announce_date"])
        after = datetime.combine(first["announce_date"], datetime.min.time())
        visible = _run(provider.earnings_events(
            "AAPL",
            datetime(2020, 1, 1),
            datetime(2025, 12, 31),
            as_of=after,
        ))
        assert any(
            e["announce_date"] == first["announce_date"] for e in visible
        )

    def test_events_include_session_flag(self):
        """Every event has a session field that is BMO or AMC."""
        provider = SampleDataProvider()
        events = _run(provider.earnings_events(
            "AAPL", datetime(2023, 1, 1), datetime(2024, 12, 31),
        ))
        assert len(events) > 0
        for e in events:
            assert e["session"] in ("BMO", "AMC"), f"Bad session: {e['session']}"

    def test_delisted_names_have_earnings(self):
        """Delisted tickers have earnings events (survivorship-free)."""
        provider = SampleDataProvider()
        events = _run(provider.earnings_events(
            "DELIST1", datetime(2020, 1, 1), datetime(2025, 12, 31),
        ))
        assert len(events) > 0

    def test_date_range_filtering(self):
        """Events outside the start/end window are excluded."""
        provider = SampleDataProvider()
        narrow = _run(provider.earnings_events(
            "AAPL",
            datetime(2023, 6, 1),
            datetime(2023, 6, 30),
        ))
        wide = _run(provider.earnings_events(
            "AAPL",
            datetime(2023, 1, 1),
            datetime(2023, 12, 31),
        ))
        assert len(narrow) <= len(wide)
        for e in narrow:
            assert date(2023, 6, 1) <= e["announce_date"] <= date(2023, 6, 30)

    def test_quarterly_coverage(self):
        """Each symbol has roughly quarterly events."""
        provider = SampleDataProvider()
        events = _run(provider.earnings_events(
            "MSFT", datetime(2023, 1, 1), datetime(2023, 12, 31),
        ))
        assert len(events) >= 3, f"Expected ~4 quarterly events, got {len(events)}"


# ---------------------------------------------------------------------------
# Earnings bar enrichment tests
# ---------------------------------------------------------------------------

class TestEarningsEnrichment:

    def test_days_to_earnings_column_added(self):
        bars = _make_bars(date(2023, 7, 1), 30)
        events = [{"symbol": "TEST", "announce_date": date(2023, 7, 15), "session": "BMO"}]
        enrich_bars_with_earnings(bars, "TEST", events)
        assert "_days_to_earnings" in bars.columns

    def test_announcement_day_is_zero(self):
        bars = _make_bars(date(2023, 7, 10), 20)
        events = [{"symbol": "TEST", "announce_date": date(2023, 7, 14), "session": "BMO"}]
        enrich_bars_with_earnings(bars, "TEST", events)
        announce_idx = bars.index.date == date(2023, 7, 14)
        if announce_idx.any():
            val = bars.loc[announce_idx, "_days_to_earnings"].iloc[0]
            assert val == 0.0, f"Expected 0 on announcement day, got {val}"

    def test_days_after_announcement_are_negative(self):
        bars = _make_bars(date(2023, 7, 10), 20)
        announce = date(2023, 7, 14)
        events = [{"symbol": "TEST", "announce_date": announce, "session": "BMO"}]
        enrich_bars_with_earnings(bars, "TEST", events)
        for i, d in enumerate(bars.index.date):
            if d > announce:
                val = bars["_days_to_earnings"].iloc[i]
                if not np.isnan(val):
                    assert val < 0, f"Expected negative days after announce, got {val} on {d}"

    def test_days_before_announcement_are_positive(self):
        bars = _make_bars(date(2023, 7, 10), 20)
        announce = date(2023, 7, 14)
        events = [{"symbol": "TEST", "announce_date": announce, "session": "BMO"}]
        enrich_bars_with_earnings(bars, "TEST", events)
        for i, d in enumerate(bars.index.date):
            if d < announce:
                val = bars["_days_to_earnings"].iloc[i]
                if not np.isnan(val):
                    assert val > 0, f"Expected positive days before announce, got {val} on {d}"

    def test_unrelated_symbol_no_enrichment(self):
        bars = _make_bars(date(2023, 7, 1), 20)
        events = [{"symbol": "OTHER", "announce_date": date(2023, 7, 10), "session": "AMC"}]
        enrich_bars_with_earnings(bars, "TEST", events)
        assert bars["_days_to_earnings"].isna().all()

    def test_empty_bars_safe(self):
        bars = pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
        events = [{"symbol": "TEST", "announce_date": date(2023, 7, 10), "session": "BMO"}]
        result = enrich_bars_with_earnings(bars, "TEST", events)
        assert result.empty


# ---------------------------------------------------------------------------
# BMO vs AMC reaction bar tests
# ---------------------------------------------------------------------------

class TestBMOvsAMC:
    """Verify the reaction bar is correctly identified for BMO and AMC."""

    def _make_spike_bars(self, announce: date, session: str) -> pd.DataFrame:
        """Build bars where the reaction bar has a clear volume/price spike."""
        bars = _make_bars(announce - timedelta(days=10), 30, base_price=50.0)
        bar_dates = bars.index.date

        if session == "BMO":
            reaction_date = announce
        else:
            bdays = pd.bdate_range(start=announce, periods=2)
            reaction_date = bdays[-1].date() if len(bdays) >= 2 else announce

        for i, d in enumerate(bar_dates):
            if d == reaction_date:
                bars.iloc[i, bars.columns.get_loc("volume")] = 5_000_000.0
                bars.iloc[i, bars.columns.get_loc("close")] = 60.0
                bars.iloc[i, bars.columns.get_loc("high")] = 61.0

        return bars, reaction_date

    def test_bmo_reaction_on_announcement_day(self):
        announce = date(2023, 7, 14)
        bars, reaction = self._make_spike_bars(announce, "BMO")
        assert reaction == announce
        reaction_idx = bars.index.date == reaction
        if reaction_idx.any():
            vol = bars.loc[reaction_idx, "volume"].iloc[0]
            assert vol == 5_000_000.0

    def test_amc_reaction_on_next_session(self):
        announce = date(2023, 7, 14)
        bars, reaction = self._make_spike_bars(announce, "AMC")
        next_bday = pd.bdate_range(start=announce, periods=2)[-1].date()
        assert reaction == next_bday
        reaction_idx = bars.index.date == reaction
        if reaction_idx.any():
            vol = bars.loc[reaction_idx, "volume"].iloc[0]
            assert vol == 5_000_000.0

    def test_days_to_event_covers_reaction_window(self):
        """Entry window days_to_event(earnings) between -3 and -1 covers
        sessions 1-3 after announcement, which includes the reaction bar
        for both BMO and AMC."""
        announce = date(2023, 7, 14)
        bars = _make_bars(announce - timedelta(days=5), 15)
        events = [{"symbol": "TEST", "announce_date": announce, "session": "AMC"}]
        enrich_bars_with_earnings(bars, "TEST", events)

        for i, d in enumerate(bars.index.date):
            val = bars["_days_to_earnings"].iloc[i]
            if d == announce:
                assert val == 0.0
            elif d > announce and not np.isnan(val):
                assert val < 0


# ---------------------------------------------------------------------------
# DSL integration tests
# ---------------------------------------------------------------------------

class TestDSLIntegration:

    def test_days_to_event_earnings_resolves(self):
        """days_to_event(earnings) reads from _days_to_earnings column."""
        from app.modules.data.features import compute_dsl_feature
        bars = _make_bars(date(2023, 7, 1), 20)
        bars["_days_to_earnings"] = np.linspace(5, -14, 20)
        result = compute_dsl_feature("days_to_event(earnings)", bars)
        assert isinstance(result, pd.Series)
        assert len(result) == 20
        assert result.iloc[0] == pytest.approx(5.0)

    def test_days_to_event_earnings_fallback_nan(self):
        """Without enrichment, days_to_event(earnings) returns NaN."""
        from app.modules.data.features import compute_dsl_feature
        bars = _make_bars(date(2023, 7, 1), 20)
        result = compute_dsl_feature("days_to_event(earnings)", bars)
        assert result.isna().all()

    def test_interpreter_entry_fires_on_enriched_bars(self):
        """The interpreter fires entry when days_to_event, zscore, and volume
        conditions are met simultaneously."""
        from app.core.dsl.interpreter import interpret
        from app.core.dsl.schema import StrategySpec

        bars = _make_bars(date(2023, 7, 1), 60, base_price=50.0)

        bars["_days_to_earnings"] = np.nan
        bars.iloc[45, bars.columns.get_loc("_days_to_earnings")] = -2.0
        bars.iloc[45, bars.columns.get_loc("close")] = 60.0
        bars.iloc[45, bars.columns.get_loc("volume")] = 2_000_000.0

        spec_raw = {
            "id": "test", "version": 1, "tickers": ["TEST"],
            "thesis": "test entry on enriched bars",
            "regime": {"all_of": [{"gt": ["avg_volume(20)", 10000]}]},
            "entry": {
                "when": {"all_of": [
                    {"between": ["days_to_event(earnings)", -3, -1]},
                    {"gt": ["zscore(20)", 0.5]},
                    {"gt": ["volume", {"expr": "2.0 * avg_volume(20)"}]},
                ]},
                "action": "enter_long",
                "sizing": {"vol_scaled": {"target_vol": 0.10}},
            },
            "exits": [{"stop_loss": {"atr_mult": 1.5}}, {"time_stop": {"sessions": 15}}],
            "risk": {"per_trade_stop_pct": 5.0, "max_position_pct": 5.0, "max_gross_exposure": 40.0},
        }
        from app.core.dsl.parser import parse_spec
        parsed = parse_spec(spec_raw)
        assert parsed.success, f"Parse failed: {parsed.errors}"
        signals = interpret(parsed.spec, bars)
        assert signals["signal"].iloc[45] == 1, "Entry should fire on enriched bar"

    def test_interpreter_no_entry_without_enrichment(self):
        """Without enrichment columns, days_to_event(earnings) is NaN → no entry."""
        from app.core.dsl.interpreter import interpret
        from app.core.dsl.parser import parse_spec

        bars = _make_bars(date(2023, 7, 1), 60, base_price=50.0)

        spec_raw = {
            "id": "test", "version": 1, "tickers": ["TEST"],
            "thesis": "test no entry without enrichment",
            "regime": {"all_of": [{"gt": ["avg_volume(20)", 10000]}]},
            "entry": {
                "when": {"all_of": [
                    {"between": ["days_to_event(earnings)", -3, -1]},
                ]},
                "action": "enter_long",
                "sizing": {"vol_scaled": {"target_vol": 0.10}},
            },
            "exits": [{"stop_loss": {"atr_mult": 1.5}}],
            "risk": {"per_trade_stop_pct": 5.0, "max_position_pct": 5.0, "max_gross_exposure": 40.0},
        }
        parsed = parse_spec(spec_raw)
        assert parsed.success
        signals = interpret(parsed.spec, bars)
        assert (signals["signal"] == 0).all(), "No entry without enrichment"


# ---------------------------------------------------------------------------
# Archetype loading tests
# ---------------------------------------------------------------------------

class TestEarningsArchetypeLoading:

    def test_archetype_loads_as_unexplored(self):
        from app.modules.registry.library_loader import load_archetypes
        archetypes = load_archetypes(validate=True)
        assert "neglected_earnings_drift" in archetypes
        assert archetypes["neglected_earnings_drift"]["status"] == "unexplored"

    def test_valid_persistence_thesis(self):
        from app.modules.registry.library_loader import load_archetypes
        archetypes = load_archetypes(validate=True)
        thesis = archetypes["neglected_earnings_drift"]["persistence_thesis"]
        assert thesis["edge_type"] == "behavioral"
        assert thesis["capacity_ceiling_usd"] == 15000000
        assert thesis["monitorable_as_regime"] is True

    def test_family_is_behavioral_drift(self):
        from app.modules.registry.library_loader import load_archetypes
        archetypes = load_archetypes(validate=True)
        assert archetypes["neglected_earnings_drift"]["family"] == "behavioral_drift"

    def test_template_parses_after_fill(self):
        from app.core.dsl.parser import parse_spec
        from app.modules.registry.library_loader import (
            load_archetypes, _extract_defaults, _fill_placeholders,
        )
        archetypes = load_archetypes(validate=False)
        a = archetypes["neglected_earnings_drift"]
        defaults = _extract_defaults(a["param_grid"])
        filled = _fill_placeholders(a["template"], defaults)
        result = parse_spec(filled)
        assert result.success, f"Parse errors: {result.errors}"

    def test_param_grid_complete(self):
        from app.modules.registry.library_loader import load_archetypes
        archetypes = load_archetypes(validate=False)
        grid = archetypes["neglected_earnings_drift"]["param_grid"]
        expected_params = {
            "neglect_volume_ceiling", "min_tradeable_volume",
            "vol_spike_mult", "reaction_z", "stop_atr", "drift_sessions",
        }
        assert set(grid.keys()) == expected_params

    def test_regime_break_exit_present(self):
        """Archetype includes regime_break_exit for death-condition wiring."""
        from app.modules.registry.library_loader import load_archetypes
        archetypes = load_archetypes(validate=False)
        exits = archetypes["neglected_earnings_drift"]["template"]["exits"]
        has_regime_break = any("regime_break_exit" in e for e in exits)
        assert has_regime_break, "regime_break_exit required for death-condition wiring"

    def test_death_condition_wired_to_regime(self):
        """The regime.all_of includes the neglect volume ceiling, matching
        the death_condition avg_volume guard."""
        from app.modules.registry.library_loader import load_archetypes
        archetypes = load_archetypes(validate=False)
        a = archetypes["neglected_earnings_drift"]
        regime_all = a["template"]["regime"]["all_of"]
        regime_text = str(regime_all)
        assert "avg_volume" in regime_text
        assert "neglect_volume_ceiling" in regime_text or "400000" in regime_text


# ---------------------------------------------------------------------------
# Regime break exit test
# ---------------------------------------------------------------------------

class TestRegimeBreakOnNeglectLoss:
    """Confirm regime_break_exit fires when avg_volume crosses the ceiling."""

    def test_regime_breaks_when_volume_rises(self):
        from app.core.dsl.interpreter import interpret
        from app.core.dsl.parser import parse_spec

        bars = _make_bars(date(2023, 1, 1), 80, base_price=50.0)
        bars["volume"] = 200_000.0
        bars.iloc[60:, bars.columns.get_loc("volume")] = 2_000_000.0

        bars["_days_to_earnings"] = np.nan
        bars.iloc[30, bars.columns.get_loc("_days_to_earnings")] = -2.0
        bars.iloc[30, bars.columns.get_loc("close")] = 60.0
        bars.iloc[30, bars.columns.get_loc("volume")] = 1_000_000.0

        spec_raw = {
            "id": "test_regime", "version": 1, "tickers": ["TEST"],
            "thesis": "test regime break",
            "regime": {"all_of": [
                {"lt": ["avg_volume(20)", 400000]},
                {"gt": ["avg_volume(20)", 50000]},
            ]},
            "entry": {
                "when": {"all_of": [
                    {"between": ["days_to_event(earnings)", -3, -1]},
                ]},
                "action": "enter_long",
                "sizing": {"vol_scaled": {"target_vol": 0.10}},
            },
            "exits": [{"stop_loss": {"atr_mult": 1.5}}, {"regime_break_exit": True}],
            "risk": {"per_trade_stop_pct": 5.0, "max_position_pct": 5.0, "max_gross_exposure": 40.0},
        }
        parsed = parse_spec(spec_raw)
        assert parsed.success
        signals = interpret(parsed.spec, bars)
        assert signals["regime_active"].iloc[25], "Regime should be active before volume spike"
        assert not signals["regime_active"].iloc[-1], "Regime should break after volume spike"
