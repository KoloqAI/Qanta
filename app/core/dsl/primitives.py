from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

class DSLType(str, Enum):
    SERIES = "Series"
    SCALAR = "Scalar"
    BOOL = "Bool"
    RECORD = "Record"
    PARAM = "Param"

@dataclass
class ParamSpec:
    type: str
    min_val: float | None = None
    max_val: float | None = None
    step: float | None = None
    default: float | None = None

@dataclass
class PrimitiveSignature:
    name: str
    args: list[tuple[str, DSLType]]
    output_type: DSLType
    output_fields: list[str] | None = None  # for Record types
    constraints: dict[str, Any] = field(default_factory=dict)

# Feature primitives catalog
FEATURE_PRIMITIVES: dict[str, PrimitiveSignature] = {
    "close": PrimitiveSignature("close", [], DSLType.SERIES),
    "open": PrimitiveSignature("open", [], DSLType.SERIES),
    "high": PrimitiveSignature("high", [], DSLType.SERIES),
    "low": PrimitiveSignature("low", [], DSLType.SERIES),
    "volume": PrimitiveSignature("volume", [], DSLType.SERIES),
    "vwap": PrimitiveSignature("vwap", [("window", DSLType.SCALAR)], DSLType.SERIES),
    "dollar_volume": PrimitiveSignature("dollar_volume", [], DSLType.SERIES),
    "sma": PrimitiveSignature("sma", [("n", DSLType.SCALAR)], DSLType.SERIES, constraints={"n": {"min": 2, "max": 400}}),
    "ema": PrimitiveSignature("ema", [("n", DSLType.SCALAR)], DSLType.SERIES, constraints={"n": {"min": 2, "max": 400}}),
    "atr": PrimitiveSignature("atr", [("n", DSLType.SCALAR)], DSLType.SERIES, constraints={"n": {"min": 2, "max": 100}}),
    "realized_vol": PrimitiveSignature("realized_vol", [("n", DSLType.SCALAR)], DSLType.SERIES, constraints={"n": {"min": 5, "max": 252}}),
    "bollinger": PrimitiveSignature("bollinger", [("n", DSLType.SCALAR), ("k", DSLType.SCALAR)], DSLType.RECORD, output_fields=["mid", "upper", "lower"], constraints={"k": {"min": 1.0, "max": 3.0}}),
    "rsi": PrimitiveSignature("rsi", [("n", DSLType.SCALAR)], DSLType.SERIES, constraints={"n": {"min": 2, "max": 50}}),
    "macd": PrimitiveSignature("macd", [("fast", DSLType.SCALAR), ("slow", DSLType.SCALAR), ("signal", DSLType.SCALAR)], DSLType.RECORD, output_fields=["macd", "signal", "hist"]),
    "adx": PrimitiveSignature("adx", [("n", DSLType.SCALAR)], DSLType.SERIES, constraints={"n": {"min": 5, "max": 50}}),
    "stochastic": PrimitiveSignature("stochastic", [("n", DSLType.SCALAR)], DSLType.RECORD, output_fields=["k", "d"]),
    "rolling_high": PrimitiveSignature("rolling_high", [("n", DSLType.SCALAR)], DSLType.SERIES),
    "rolling_low": PrimitiveSignature("rolling_low", [("n", DSLType.SCALAR)], DSLType.SERIES),
    "range_detect": PrimitiveSignature("range_detect", [("n", DSLType.SCALAR)], DSLType.RECORD, output_fields=["low", "high", "in_range"]),
    "zscore": PrimitiveSignature("zscore", [("n", DSLType.SCALAR)], DSLType.SERIES),
    "avg_volume": PrimitiveSignature("avg_volume", [("n", DSLType.SCALAR)], DSLType.SERIES),
    "time_of_day": PrimitiveSignature("time_of_day", [], DSLType.SERIES),
    "session_phase": PrimitiveSignature("session_phase", [], DSLType.SERIES),
    "days_to_event": PrimitiveSignature("days_to_event", [("kind", DSLType.SCALAR)], DSLType.SERIES),
    "is_index_add": PrimitiveSignature("is_index_add", [], DSLType.SERIES),
    "is_index_delete": PrimitiveSignature("is_index_delete", [], DSLType.SERIES),
}

DSL_VOCABULARY_VERSION = 2

# Condition primitives catalog
CONDITION_PRIMITIVES: dict[str, PrimitiveSignature] = {
    "eq": PrimitiveSignature("eq", [("a", DSLType.SERIES), ("b", DSLType.SERIES)], DSLType.BOOL),
    "gt": PrimitiveSignature("gt", [("a", DSLType.SERIES), ("b", DSLType.SERIES)], DSLType.BOOL),
    "lt": PrimitiveSignature("lt", [("a", DSLType.SERIES), ("b", DSLType.SERIES)], DSLType.BOOL),
    "between": PrimitiveSignature("between", [("a", DSLType.SERIES), ("lo", DSLType.SCALAR), ("hi", DSLType.SCALAR)], DSLType.BOOL),
    "crosses_above": PrimitiveSignature("crosses_above", [("a", DSLType.SERIES), ("b", DSLType.SERIES)], DSLType.BOOL),
    "crosses_below": PrimitiveSignature("crosses_below", [("a", DSLType.SERIES), ("b", DSLType.SERIES)], DSLType.BOOL),
    "within_band": PrimitiveSignature("within_band", [("a", DSLType.SERIES), ("lo", DSLType.SERIES), ("hi", DSLType.SERIES)], DSLType.BOOL),
    "outside_band": PrimitiveSignature("outside_band", [("a", DSLType.SERIES), ("lo", DSLType.SERIES), ("hi", DSLType.SERIES)], DSLType.BOOL),
    "held_for": PrimitiveSignature("held_for", [("cond", DSLType.BOOL), ("n", DSLType.SCALAR)], DSLType.BOOL),
    "all_of": PrimitiveSignature("all_of", [("conditions", DSLType.BOOL)], DSLType.BOOL),
    "any_of": PrimitiveSignature("any_of", [("conditions", DSLType.BOOL)], DSLType.BOOL),
    "not": PrimitiveSignature("not", [("cond", DSLType.BOOL)], DSLType.BOOL),
}

ALL_PRIMITIVES: dict[str, PrimitiveSignature] = {**FEATURE_PRIMITIVES, **CONDITION_PRIMITIVES}
