"""M4 Gate Tests -- Strategy DSL type-checking.

Gate: a valid spec type-checks and runs through M2+M3;
a malformed/out-of-vocabulary spec is rejected at parse time.
"""
from __future__ import annotations

import pytest
from app.core.dsl.parser import parse_spec


def _valid_spec_raw() -> dict:
    return {
        "id": "m4-test",
        "version": 1,
        "tickers": ["AAPL"],
        "thesis": "SMA crossover in uptrend",
        "regime": {"all_of": [{"gt": ["sma(50)", "sma(200)"]}]},
        "entry": {
            "when": {"crosses_above": ["sma(20)", "sma(50)"]},
            "action": "enter_long",
            "sizing": {"fixed_pct": {"pct": 5.0}},
        },
        "exits": [
            {"stop_loss": {"pct": 3.0}},
            {"take_profit": {"pct": 6.0}},
        ],
        "risk": {
            "max_position_pct": 5.0,
            "per_trade_stop_pct": 3.0,
            "max_gross_exposure": 40.0,
        },
        "universe": {"primary": "AAPL"},
        "validation": {"targets": [{"R": 0.02, "H": 7}]},
    }


def test_valid_spec_passes():
    result = parse_spec(_valid_spec_raw())
    assert result.success
    assert result.spec is not None
    assert result.spec.thesis == "SMA crossover in uptrend"


def test_unknown_top_level_field_rejected():
    raw = _valid_spec_raw()
    raw["bogus_field"] = "should fail"
    result = parse_spec(raw)
    assert not result.success
    assert any("Unknown top-level" in e.message for e in (result.errors or []))


def test_missing_thesis_rejected():
    raw = _valid_spec_raw()
    del raw["thesis"]
    result = parse_spec(raw)
    assert not result.success
    assert any(e.field == "thesis" for e in (result.errors or []))


def test_empty_thesis_rejected():
    raw = _valid_spec_raw()
    raw["thesis"] = ""
    result = parse_spec(raw)
    assert not result.success
    assert any(e.field == "thesis" for e in (result.errors or []))


def test_empty_regime_rejected():
    raw = _valid_spec_raw()
    raw["regime"] = {"all_of": []}
    result = parse_spec(raw)
    assert not result.success
    assert any(e.field == "regime" for e in (result.errors or []))


def test_missing_stop_loss_rejected():
    raw = _valid_spec_raw()
    raw["exits"] = [{"take_profit": {"pct": 5.0}}]
    result = parse_spec(raw)
    assert not result.success
    assert any(e.field == "exits" for e in (result.errors or []))


def test_unknown_condition_operator_rejected():
    raw = _valid_spec_raw()
    raw["regime"] = {"all_of": [{"bogus_op": ["close", 100]}]}
    result = parse_spec(raw)
    assert not result.success
    assert any("Unknown condition" in e.message for e in (result.errors or []))


def test_unknown_action_rejected():
    raw = _valid_spec_raw()
    raw["entry"]["action"] = "enter_diagonal"
    result = parse_spec(raw)
    assert not result.success
    assert any("Unknown action" in e.message for e in (result.errors or []))


def test_risk_exceeding_guardrails_rejected():
    raw = _valid_spec_raw()
    raw["risk"]["max_position_pct"] = 50.0  # exceeds guardrail
    result = parse_spec(raw)
    assert not result.success
    assert any("exceeds guardrail" in e.message for e in (result.errors or []))


def test_risk_stop_pct_exceeding_guardrails_rejected():
    raw = _valid_spec_raw()
    raw["risk"]["per_trade_stop_pct"] = 10.0  # exceeds 5.0 guardrail
    result = parse_spec(raw)
    assert not result.success
    assert any("per_trade_stop_pct" in e.field for e in (result.errors or []))


def test_risk_gross_exposure_exceeding_guardrails_rejected():
    raw = _valid_spec_raw()
    raw["risk"]["max_gross_exposure"] = 200.0  # exceeds 100.0 guardrail
    result = parse_spec(raw)
    assert not result.success
    assert any("max_gross_exposure" in e.field for e in (result.errors or []))


def test_unknown_exit_type_rejected():
    raw = _valid_spec_raw()
    raw["exits"].append({"magic_exit": {"threshold": 0.5}})
    result = parse_spec(raw)
    assert not result.success
    assert any("Unknown exit type" in e.message for e in (result.errors or []))


def test_unknown_primitive_rejected():
    raw = _valid_spec_raw()
    raw["regime"] = {"all_of": [{"gt": ["fake_indicator(14)", "sma(50)"]}]}
    result = parse_spec(raw)
    assert not result.success
    assert any("Unknown primitive" in e.message for e in (result.errors or []))


def test_primitive_wrong_arity_rejected():
    raw = _valid_spec_raw()
    # sma expects 1 arg, giving 2
    raw["regime"] = {"all_of": [{"gt": ["sma(50,100)", "sma(200)"]}]}
    result = parse_spec(raw)
    assert not result.success
    assert any("expects" in e.message and "arg" in e.message for e in (result.errors or []))


def test_primitive_param_out_of_range_rejected():
    raw = _valid_spec_raw()
    # sma n constraint: min=2, max=400; use 1 which is below min
    raw["regime"] = {"all_of": [{"gt": ["sma(1)", "sma(200)"]}]}
    result = parse_spec(raw)
    assert not result.success
    assert any("below minimum" in e.message for e in (result.errors or []))


def test_primitive_param_above_max_rejected():
    raw = _valid_spec_raw()
    # sma n constraint: min=2, max=400; use 500 which is above max
    raw["regime"] = {"all_of": [{"gt": ["sma(500)", "sma(200)"]}]}
    result = parse_spec(raw)
    assert not result.success
    assert any("exceeds maximum" in e.message for e in (result.errors or []))


def test_record_field_access_valid():
    raw = _valid_spec_raw()
    raw["entry"]["when"] = {
        "gt": ["bollinger(20,2).upper", "close"],
    }
    result = parse_spec(raw)
    assert result.success


def test_record_field_access_invalid_field():
    raw = _valid_spec_raw()
    raw["entry"]["when"] = {
        "gt": ["bollinger(20,2).nonexistent", "close"],
    }
    result = parse_spec(raw)
    assert not result.success
    assert any("no field" in e.message for e in (result.errors or []))


def test_condition_gt_wrong_arg_count():
    raw = _valid_spec_raw()
    raw["regime"] = {"all_of": [{"gt": ["sma(50)"]}]}  # needs 2 args
    result = parse_spec(raw)
    assert not result.success
    assert any("requires exactly 2" in e.message for e in (result.errors or []))


def test_condition_between_wrong_arg_count():
    raw = _valid_spec_raw()
    raw["entry"]["when"] = {"between": ["rsi(14)", 30]}  # needs 3 args
    result = parse_spec(raw)
    assert not result.success
    assert any("requires exactly 3" in e.message for e in (result.errors or []))


def test_unknown_entry_field_rejected():
    raw = _valid_spec_raw()
    raw["entry"]["bogus"] = "should fail"
    result = parse_spec(raw)
    assert not result.success
    assert any("Unknown entry field" in e.message for e in (result.errors or []))


def test_unknown_sizing_method_rejected():
    raw = _valid_spec_raw()
    raw["entry"]["sizing"] = {"quantum_sizing": 5.0}
    result = parse_spec(raw)
    assert not result.success
    assert any("Unknown sizing" in e.message for e in (result.errors or []))


def test_multiple_errors_collected():
    """Parser collects all errors, not just the first one."""
    raw = {
        "bogus_top": True,
        "regime": {"all_of": []},
        "exits": [],
    }
    result = parse_spec(raw)
    assert not result.success
    # Should have at least: unknown field, missing thesis, empty regime, missing stop_loss
    assert len(result.errors or []) >= 4


def test_held_for_condition_validated():
    raw = _valid_spec_raw()
    raw["entry"]["when"] = {
        "held_for": [{"gt": ["sma(20)", "sma(50)"]}, 5],
    }
    result = parse_spec(raw)
    assert result.success


def test_held_for_wrong_arity():
    raw = _valid_spec_raw()
    raw["entry"]["when"] = {"held_for": [{"gt": ["sma(20)", "sma(50)"]}]}
    result = parse_spec(raw)
    assert not result.success
    assert any("held_for" in e.message for e in (result.errors or []))


def test_all_of_requires_list():
    raw = _valid_spec_raw()
    raw["regime"] = {"all_of": [{"all_of": "not_a_list"}]}
    result = parse_spec(raw)
    assert not result.success
    assert any("requires a list" in e.message for e in (result.errors or []))


def test_risk_at_guardrail_boundary_passes():
    """Risk values exactly at the guardrail limit should pass."""
    raw = _valid_spec_raw()
    raw["risk"]["max_position_pct"] = 10.0  # exactly at guardrail
    raw["risk"]["per_trade_stop_pct"] = 5.0  # exactly at guardrail
    raw["risk"]["max_gross_exposure"] = 100.0  # exactly at guardrail
    result = parse_spec(raw)
    assert result.success


@pytest.mark.asyncio
async def test_valid_spec_runs_through_backtest():
    """A valid spec can be parsed and backtested (M2+M4 integration)."""
    raw = _valid_spec_raw()
    result = parse_spec(raw)
    assert result.success

    from app.modules.data.providers import SampleDataProvider
    from app.modules.backtest.service import BacktesterImpl
    from datetime import datetime

    provider = SampleDataProvider()
    bars = await provider.bars("AAPL", datetime(2020, 1, 1), datetime(2022, 1, 1))
    bt = BacktesterImpl()
    bt_result = await bt.run(result.spec, bars)
    assert bt_result.n_trades >= 0
