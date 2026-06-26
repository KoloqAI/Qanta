"""Unit tests for the reconstitution calendar, event enrichment, and DSL extensions.

Covers:
- Point-in-time reconstitution calendar (SampleDataProvider)
- Event enrichment of bars (is_index_add, is_index_delete, days_to_event)
- `eq` condition primitive in parser, interpreter, and scan evaluation
- `is_index_add` / `is_index_delete` features end-to-end
- Interpreter parity (same bars → same signals in two invocations)
- Archetype loading (persistence thesis gate + param binding + variant distinctness)
"""
from __future__ import annotations

import copy
from datetime import datetime, date, timedelta

import numpy as np
import pandas as pd
import pytest

from app.modules.data.providers import SampleDataProvider
from app.modules.data.events import enrich_bars_with_events, _business_days_between
from app.modules.data.features import compute_dsl_feature, evaluate_condition, evaluate_scan_block
from app.core.dsl.parser import parse_spec
from app.core.dsl.interpreter import interpret
from app.core.dsl.primitives import FEATURE_PRIMITIVES, CONDITION_PRIMITIVES, DSL_VOCABULARY_VERSION
from app.modules.registry.library_loader import load_archetypes, _fill_placeholders, _extract_defaults


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SAMPLE_EVENTS = [
    {
        "symbol": "RECON_ADD1",
        "index": "russell_2000",
        "action": "add",
        "preliminary_list_date": date(2024, 5, 31),
        "final_list_date": date(2024, 6, 14),
        "effective_date": date(2024, 6, 28),
    },
    {
        "symbol": "RECON_DEL1",
        "index": "russell_2000",
        "action": "delete",
        "preliminary_list_date": date(2024, 5, 31),
        "final_list_date": date(2024, 6, 14),
        "effective_date": date(2024, 6, 28),
    },
]


def _make_bars(start: str, end: str, close: float = 100.0) -> pd.DataFrame:
    dates = pd.bdate_range(start=start, end=end)
    n = len(dates)
    rng = np.random.default_rng(42)
    c = np.full(n, close) + rng.normal(0, 0.5, n)
    return pd.DataFrame(
        {
            "open": c * 0.99,
            "high": c * 1.01,
            "low": c * 0.98,
            "close": c,
            "volume": np.full(n, 500_000.0),
        },
        index=dates,
    )


# ---------------------------------------------------------------------------
# 1. Point-in-time reconstitution calendar
# ---------------------------------------------------------------------------


class TestReconstitutionCalendar:
    @pytest.mark.asyncio
    async def test_events_visible_after_final_list_date(self):
        provider = SampleDataProvider()
        events = await provider.reconstitution_events(
            "russell_2000",
            as_of=datetime(2024, 6, 20),
        )
        adds = [e for e in events if e["action"] == "add" and "2024" in str(e["effective_date"])]
        assert len(adds) >= 1, "Events should be visible after final_list_date"

    @pytest.mark.asyncio
    async def test_events_hidden_before_final_list_date(self):
        """as_of < final_list_date → event not visible (prevents lookahead)."""
        provider = SampleDataProvider()
        events = await provider.reconstitution_events(
            "russell_2000",
            as_of=datetime(2024, 6, 13),
        )
        adds_2024 = [
            e for e in events
            if e["action"] == "add" and e["effective_date"].year == 2024
        ]
        assert len(adds_2024) == 0, (
            "Events must NOT be visible before final_list_date — lookahead violation"
        )

    @pytest.mark.asyncio
    async def test_events_filtered_by_index(self):
        provider = SampleDataProvider()
        events = await provider.reconstitution_events(
            "sp500",
            as_of=datetime(2024, 7, 1),
        )
        assert len(events) == 0, "No S&P 500 events in sample data"

    @pytest.mark.asyncio
    async def test_events_filtered_by_date_range(self):
        provider = SampleDataProvider()
        events = await provider.reconstitution_events(
            "russell_2000",
            as_of=datetime(2024, 7, 1),
            start=datetime(2024, 1, 1),
            end=datetime(2024, 12, 31),
        )
        for e in events:
            assert e["effective_date"].year == 2024

    @pytest.mark.asyncio
    async def test_delisted_names_included(self):
        provider = SampleDataProvider()
        events = await provider.reconstitution_events(
            "russell_2000",
            as_of=datetime(2024, 7, 1),
        )
        symbols = {e["symbol"] for e in events}
        assert "DELIST1" in symbols, "Delisted names must be included (survivorship-free)"


# ---------------------------------------------------------------------------
# 2. Event enrichment
# ---------------------------------------------------------------------------


class TestEventEnrichment:
    def test_is_index_add_set_between_final_and_effective(self):
        bars = _make_bars("2024-06-01", "2024-07-05")
        enrich_bars_with_events(bars, "RECON_ADD1", SAMPLE_EVENTS)

        for i, d in enumerate(bars.index):
            bd = d.date()
            expected = 1.0 if date(2024, 6, 14) <= bd <= date(2024, 6, 28) else 0.0
            assert bars["_is_index_add"].iloc[i] == expected, (
                f"Date {bd}: expected is_index_add={expected}, got {bars['_is_index_add'].iloc[i]}"
            )

    def test_is_index_delete_set_for_delete_action(self):
        bars = _make_bars("2024-06-01", "2024-07-05")
        enrich_bars_with_events(bars, "RECON_DEL1", SAMPLE_EVENTS)

        assert bars["_is_index_delete"].sum() > 0, "Should have some delete flags"
        assert bars["_is_index_add"].sum() == 0, "RECON_DEL1 is a delete, not add"

    def test_days_to_effective_countdown(self):
        bars = _make_bars("2024-06-14", "2024-06-28")
        enrich_bars_with_events(bars, "RECON_ADD1", SAMPLE_EVENTS)

        assert "_days_to_russell_effective" in bars.columns
        first_val = bars["_days_to_russell_effective"].iloc[0]
        last_val = bars["_days_to_russell_effective"].iloc[-1]
        assert first_val > last_val, "Days should count down"
        assert last_val == 0.0, "On effective date, days_to should be 0"

    def test_no_enrichment_for_unrelated_symbol(self):
        bars = _make_bars("2024-06-01", "2024-07-05")
        enrich_bars_with_events(bars, "AAPL", SAMPLE_EVENTS)

        assert bars["_is_index_add"].sum() == 0
        assert bars["_is_index_delete"].sum() == 0
        assert bars["_days_to_russell_effective"].isna().all()

    def test_empty_bars_handled(self):
        bars = pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
        result = enrich_bars_with_events(bars, "RECON_ADD1", SAMPLE_EVENTS)
        assert result.empty


class TestBusinessDays:
    def test_same_day(self):
        assert _business_days_between(date(2024, 6, 14), date(2024, 6, 14)) == 0

    def test_one_business_day(self):
        assert _business_days_between(date(2024, 6, 14), date(2024, 6, 17)) == 1

    def test_over_weekend(self):
        result = _business_days_between(date(2024, 6, 14), date(2024, 6, 21))
        assert result == 5


# ---------------------------------------------------------------------------
# 3. DSL `eq` condition primitive
# ---------------------------------------------------------------------------


class TestEqCondition:
    def test_eq_in_condition_primitives(self):
        assert "eq" in CONDITION_PRIMITIVES

    def test_eq_parser_accepts(self):
        spec_raw = {
            "id": "", "version": 1, "tickers": ["AAPL"],
            "thesis": "Test eq condition",
            "regime": {"all_of": [{"gt": ["sma(50)", "sma(200)"]}]},
            "entry": {
                "when": {"eq": ["is_index_add", 1]},
                "action": "enter_long",
                "sizing": {"fixed_pct": {"pct": 5.0}},
            },
            "exits": [{"stop_loss": {"pct": 3.0}}],
            "risk": {"max_position_pct": 5.0, "per_trade_stop_pct": 3.0,
                     "max_gross_exposure": 40.0},
        }
        result = parse_spec(spec_raw)
        assert result.success, f"eq should be accepted: {result.errors}"

    def test_eq_interpreter_evaluates(self):
        bars = _make_bars("2024-06-01", "2024-06-30")
        bars["_is_index_add"] = 0.0
        bars.loc[bars.index[5:10], "_is_index_add"] = 1.0

        features = {"is_index_add": bars["_is_index_add"]}
        from app.core.dsl.interpreter import _evaluate_condition

        result = _evaluate_condition(
            {"eq": ["is_index_add", 1]}, features, bars,
        )
        assert result.iloc[5] is True or result.iloc[5] == True
        assert result.iloc[0] is False or result.iloc[0] == False

    def test_eq_scan_evaluation(self):
        bars = _make_bars("2024-06-01", "2024-06-30")
        bars["_is_index_add"] = 0.0
        bars.iloc[-1, bars.columns.get_loc("_is_index_add")] = 1.0

        passed, score = evaluate_condition({"eq": ["is_index_add", 1]}, bars)
        assert passed, "eq should pass when last bar has is_index_add=1"


# ---------------------------------------------------------------------------
# 4. Event features in DSL catalog
# ---------------------------------------------------------------------------


class TestEventFeatures:
    def test_is_index_add_in_catalog(self):
        assert "is_index_add" in FEATURE_PRIMITIVES
        assert FEATURE_PRIMITIVES["is_index_add"].args == []

    def test_is_index_delete_in_catalog(self):
        assert "is_index_delete" in FEATURE_PRIMITIVES

    def test_days_to_event_in_catalog(self):
        assert "days_to_event" in FEATURE_PRIMITIVES

    def test_dsl_vocabulary_version_bumped(self):
        assert DSL_VOCABULARY_VERSION >= 2

    def test_old_v1_spec_unaffected_by_version_bump(self):
        """A spec using only v1 features must still parse and interpret after the v2 bump."""
        v1_spec_raw = {
            "id": "v1_compat", "version": 1, "tickers": ["AAPL"],
            "thesis": "V1 spec uses only pre-v2 primitives",
            "regime": {"all_of": [{"gt": ["sma(50)", "sma(200)"]}]},
            "entry": {
                "when": {"crosses_above": ["rsi(14)", 30]},
                "action": "enter_long",
                "sizing": {"fixed_pct": {"pct": 5.0}},
            },
            "exits": [{"stop_loss": {"atr_mult": 1.5}}],
            "risk": {"max_position_pct": 5.0, "per_trade_stop_pct": 5.0,
                     "max_gross_exposure": 40.0},
        }
        result = parse_spec(v1_spec_raw)
        assert result.success, f"V1 spec should still parse after v2 bump: {result.errors}"

        bars = _make_bars("2024-01-01", "2024-06-30")
        signals = interpret(result.spec, bars)
        assert len(signals) == len(bars), "V1 spec should interpret to same-length output"
        assert "signal" in signals.columns


# ---------------------------------------------------------------------------
# 5. Interpreter parity
# ---------------------------------------------------------------------------


class TestInterpreterParity:
    def test_same_bars_same_signals(self):
        """Identical enriched bars must produce identical signals (deterministic)."""
        bars = _make_bars("2024-06-01", "2024-07-05")
        enrich_bars_with_events(bars, "RECON_ADD1", SAMPLE_EVENTS)

        spec_raw = {
            "id": "parity_test", "version": 1, "tickers": ["RECON_ADD1"],
            "thesis": "Test parity",
            "regime": {"all_of": [{"gt": ["avg_volume(20)", 100000]}]},
            "entry": {
                "when": {"all_of": [
                    {"eq": ["is_index_add", 1]},
                    {"between": ["days_to_event(russell_effective)", 1, 10]},
                ]},
                "action": "enter_long",
                "sizing": {"vol_scaled": {"target_vol": 0.08}},
            },
            "exits": [{"stop_loss": {"atr_mult": 1.5}}, {"time_stop": {"sessions": 8}}],
            "risk": {"max_position_pct": 5.0, "per_trade_stop_pct": 5.0,
                     "max_gross_exposure": 40.0},
        }
        result = parse_spec(spec_raw)
        assert result.success, f"Parse failed: {result.errors}"

        signals_1 = interpret(result.spec, bars.copy())
        signals_2 = interpret(result.spec, bars.copy())

        pd.testing.assert_frame_equal(signals_1, signals_2)


# ---------------------------------------------------------------------------
# 6. Archetype loading
# ---------------------------------------------------------------------------


class TestReconstitutionArchetypeLoading:
    def test_archetype_loads_with_unexplored_status(self):
        archetypes = load_archetypes(validate=True)
        assert "russell_reconstitution_drift" in archetypes
        a = archetypes["russell_reconstitution_drift"]
        assert a["status"] == "unexplored", (
            f"Expected 'unexplored', got '{a['status']}'. "
            f"Exclusion reason: {a.get('exclusion_reason', 'none')}"
        )

    def test_archetype_has_valid_persistence_thesis(self):
        archetypes = load_archetypes(validate=True)
        a = archetypes["russell_reconstitution_drift"]
        pt = a.get("persistence_thesis")
        assert pt is not None
        assert pt["edge_type"] == "forced_flow"
        assert len(pt["structural_reason"].strip()) >= 40
        assert len(pt["forced_counterparty"].strip()) >= 40
        assert len(pt["death_condition"]) >= 1
        assert pt["capacity_ceiling_usd"] > 0
        assert pt["monitorable_as_regime"] is True

    def test_archetype_family_is_forced_flow(self):
        archetypes = load_archetypes(validate=True)
        a = archetypes["russell_reconstitution_drift"]
        assert a["family"] == "forced_flow"

    def test_archetype_template_fills_and_parses(self):
        archetypes = load_archetypes(validate=True)
        a = archetypes["russell_reconstitution_drift"]
        template = copy.deepcopy(a["template"])
        template["tickers"] = ["RECON_ADD1"]
        template.setdefault("universe", {})["primary"] = "RECON_ADD1"
        template.setdefault("validation", {"targets": [{"R": 0.02, "H": 7}]})
        defaults = _extract_defaults(a["param_grid"])
        filled = _fill_placeholders(template, defaults)
        result = parse_spec(filled)
        assert result.success, f"Parse failed: {result.errors}"

    def test_archetype_param_grid_complete(self):
        archetypes = load_archetypes(validate=True)
        a = archetypes["russell_reconstitution_drift"]
        grid = a["param_grid"]
        expected_params = {
            "enter_min_days", "enter_max_days", "hold_sessions",
            "stop_atr", "capacity_volume_ceiling", "min_tradeable_volume",
        }
        assert set(grid.keys()) == expected_params


# ---------------------------------------------------------------------------
# 7. Negative/positive control helpers
# (Full T2 controls are in integration tests)
# ---------------------------------------------------------------------------


class TestEventFeatureComputation:
    def test_is_index_add_feature_returns_series(self):
        bars = _make_bars("2024-06-01", "2024-07-05")
        enrich_bars_with_events(bars, "RECON_ADD1", SAMPLE_EVENTS)
        result = compute_dsl_feature("is_index_add", bars)
        assert isinstance(result, pd.Series)
        assert result.sum() > 0

    def test_days_to_event_feature_returns_series(self):
        bars = _make_bars("2024-06-14", "2024-06-28")
        enrich_bars_with_events(bars, "RECON_ADD1", SAMPLE_EVENTS)
        result = compute_dsl_feature("days_to_event(russell_effective)", bars)
        assert isinstance(result, pd.Series)
        assert not result.isna().all(), "Should have some non-NaN days"

    def test_is_index_add_fallback_to_zero_without_enrichment(self):
        bars = _make_bars("2024-06-01", "2024-06-30")
        result = compute_dsl_feature("is_index_add", bars)
        assert isinstance(result, pd.Series)
        assert (result == 0.0).all()

    def test_days_to_event_fallback_to_nan_without_enrichment(self):
        bars = _make_bars("2024-06-01", "2024-06-30")
        result = compute_dsl_feature("days_to_event(russell_effective)", bars)
        assert isinstance(result, pd.Series)
        assert result.isna().all()

    def test_entry_fires_on_enriched_bars(self):
        """Verify the interpreter generates entry signals on enriched bars."""
        bars = _make_bars("2024-06-01", "2024-07-05")
        enrich_bars_with_events(bars, "RECON_ADD1", SAMPLE_EVENTS)

        spec_raw = {
            "id": "entry_test", "version": 1, "tickers": ["RECON_ADD1"],
            "thesis": "Test entry fires",
            "regime": {"all_of": [{"gt": ["avg_volume(20)", 100000]}]},
            "entry": {
                "when": {"all_of": [
                    {"eq": ["is_index_add", 1]},
                    {"between": ["days_to_event(russell_effective)", 1, 10]},
                ]},
                "action": "enter_long",
                "sizing": {"fixed_pct": {"pct": 5.0}},
            },
            "exits": [{"stop_loss": {"atr_mult": 1.5}}],
            "risk": {"max_position_pct": 5.0, "per_trade_stop_pct": 5.0,
                     "max_gross_exposure": 40.0},
        }
        result = parse_spec(spec_raw)
        assert result.success

        signals = interpret(result.spec, bars)
        entry_count = (signals["signal"] == 1).sum()
        assert entry_count > 0, (
            "Entry should fire on bars where is_index_add=1 and days_to_event in [1,10]"
        )

    def test_no_entry_on_unenriched_bars(self):
        """Without event enrichment, no entry signals fire."""
        bars = _make_bars("2024-06-01", "2024-07-05")

        spec_raw = {
            "id": "no_entry", "version": 1, "tickers": ["AAPL"],
            "thesis": "Test no entry without events",
            "regime": {"all_of": [{"gt": ["avg_volume(20)", 100000]}]},
            "entry": {
                "when": {"eq": ["is_index_add", 1]},
                "action": "enter_long",
                "sizing": {"fixed_pct": {"pct": 5.0}},
            },
            "exits": [{"stop_loss": {"pct": 3.0}}],
            "risk": {"max_position_pct": 5.0, "per_trade_stop_pct": 3.0,
                     "max_gross_exposure": 40.0},
        }
        result = parse_spec(spec_raw)
        assert result.success

        signals = interpret(result.spec, bars)
        assert (signals["signal"] == 0).all(), "No entry without event enrichment"
