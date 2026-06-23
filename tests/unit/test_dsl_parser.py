from __future__ import annotations

from app.core.dsl.parser import parse_spec


def test_parse_valid_spec():
    raw = {
        "id": "test-1",
        "version": 1,
        "tickers": ["AAPL"],
        "thesis": "Mean reversion in a defined range",
        "regime": {"all_of": [{"gt": ["avg_volume(20)", 1000000]}]},
        "entry": {"when": {"lt": ["rsi(14)", 30]}, "action": "enter_long", "sizing": {"fixed_pct": {"pct": 5.0}}},
        "exits": [{"stop_loss": {"atr_mult": 1.5}}],
        "risk": {"max_position_pct": 5.0, "per_trade_stop_pct": 3.0, "max_gross_exposure": 40.0},
        "universe": {"primary": "AAPL", "peers": ["MSFT", "GOOGL"]},
        "validation": {"targets": [{"R": 0.02, "H": 7}]},
    }
    result = parse_spec(raw)
    assert result.success
    assert result.spec is not None
    assert result.spec.thesis == "Mean reversion in a defined range"


def test_parse_missing_thesis():
    raw = {
        "regime": {"all_of": [{"gt": ["volume", 100]}]},
        "exits": [{"stop_loss": {"pct": 2.0}}],
    }
    result = parse_spec(raw)
    assert not result.success
    assert any(e.field == "thesis" for e in (result.errors or []))


def test_parse_missing_stop_loss():
    raw = {
        "thesis": "Some thesis",
        "regime": {"all_of": [{"gt": ["volume", 100]}]},
        "exits": [{"take_profit": {"pct": 5.0}}],
    }
    result = parse_spec(raw)
    assert not result.success
    assert any(e.field == "exits" for e in (result.errors or []))


def test_parse_empty_regime():
    raw = {
        "thesis": "Some thesis",
        "regime": {"all_of": []},
        "exits": [{"stop_loss": {"pct": 2.0}}],
    }
    result = parse_spec(raw)
    assert not result.success
    assert any(e.field == "regime" for e in (result.errors or []))
