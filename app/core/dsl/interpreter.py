from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from app.core.dsl.schema import StrategySpec


def interpret(spec: StrategySpec, bars: pd.DataFrame) -> pd.DataFrame:
    """Pure deterministic interpretation: spec + bars -> signals.

    No I/O, no randomness, no LLM. Same function feeds the backtester
    (historical bars) and the execution runtime (live bars).

    Returns a DataFrame with columns:
    - signal: 1 (enter long), -1 (enter short), 0 (no action)
    - regime_active: bool — whether regime conditions hold
    - stop_loss: float — stop level for the position
    - take_profit: float | NaN — take profit level
    - position_size_pct: float — sizing as pct of equity
    """
    from app.modules.data.features import FeatureComputer as fc

    n = len(bars)
    result = pd.DataFrame(
        {
            "signal": np.zeros(n, dtype=int),
            "regime_active": np.zeros(n, dtype=bool),
            "stop_loss": np.full(n, np.nan),
            "take_profit": np.full(n, np.nan),
            "position_size_pct": np.zeros(n, dtype=float),
        },
        index=bars.index,
    )

    if n == 0:
        return result

    # Pre-compute features that the spec references
    features = _compute_features(spec, bars)

    # Evaluate regime conditions
    regime_active = _evaluate_regime(spec.regime, features, bars)
    result["regime_active"] = regime_active

    # Evaluate entry conditions
    entry_signal = _evaluate_entry(spec.entry, features, bars)

    # Combine: entry only when regime is active
    result["signal"] = np.where(regime_active & entry_signal, _entry_direction(spec.entry), 0)

    # Compute exit levels
    _compute_exits(spec, bars, features, result)

    # Compute sizing
    _compute_sizing(spec, bars, features, result)

    return result


def _resolve_value(ref: Any, features: dict[str, Any], bars: pd.DataFrame) -> Any:
    """Resolve a DSL reference to a concrete Series or scalar."""
    if isinstance(ref, (int, float)):
        return ref
    if isinstance(ref, str):
        # Direct column reference
        if ref in ("close", "open", "high", "low", "volume"):
            return bars[ref]
        # Feature reference like "sma(20)" or "rsi(14)"
        if ref in features:
            return features[ref]
        # Record field access like "bollinger(20,2).upper"
        if "." in ref:
            base, field = ref.rsplit(".", 1)
            if base in features and isinstance(features[base], dict):
                return features[base][field]
        return ref
    if isinstance(ref, dict) and "expr" in ref:
        return _eval_expr(ref["expr"], features, bars)
    return ref


def _eval_expr(expr: str, features: dict[str, Any], bars: pd.DataFrame) -> Any:
    """Evaluate a simple arithmetic expression over features.

    Supports: feature references, +, -, *, / with numeric constants.
    NOT a general eval — only safe, limited arithmetic.
    """
    import re

    expr = expr.strip()

    # Try to resolve as a direct feature reference first
    resolved = _resolve_value(expr, features, bars)
    if not isinstance(resolved, str):
        return resolved

    # Handle "feature + constant" and "feature * constant" patterns
    for op_str, op_fn in [("+", lambda a, b: a + b), ("-", lambda a, b: a - b),
                          ("*", lambda a, b: a * b), ("/", lambda a, b: a / b)]:
        if op_str in expr:
            parts = expr.split(op_str, 1)
            if len(parts) == 2:
                left = _resolve_value(parts[0].strip(), features, bars)
                right = _resolve_value(parts[1].strip(), features, bars)
                if left is not None and right is not None:
                    try:
                        return op_fn(left, right)
                    except Exception:
                        pass

    return np.nan


def _parse_feature_ref(ref: str) -> tuple[str, list[Any]] | None:
    """Parse 'sma(20)' -> ('sma', [20])."""
    import re
    m = re.match(r"(\w+)\(([^)]*)\)", ref)
    if not m:
        return None
    name = m.group(1)
    args_str = m.group(2)
    args: list[Any] = []
    for a in args_str.split(","):
        a = a.strip()
        if not a:
            continue
        try:
            args.append(int(a))
        except ValueError:
            try:
                args.append(float(a))
            except ValueError:
                args.append(a)
    return name, args


def _compute_features(spec: StrategySpec, bars: pd.DataFrame) -> dict[str, Any]:
    """Pre-compute all features referenced in the spec."""
    from app.modules.data.features import FeatureComputer as fc

    features: dict[str, Any] = {}
    refs = _collect_refs(spec)

    for ref in refs:
        parsed = _parse_feature_ref(ref)
        if parsed is None:
            continue
        name, args = parsed

        if name == "sma" and len(args) >= 1:
            features[ref] = fc.sma(bars["close"], int(args[0]))
        elif name == "ema" and len(args) >= 1:
            features[ref] = fc.ema(bars["close"], int(args[0]))
        elif name == "rsi" and len(args) >= 1:
            features[ref] = fc.rsi(bars["close"], int(args[0]))
        elif name == "atr" and len(args) >= 1:
            features[ref] = fc.atr(bars["high"], bars["low"], bars["close"], int(args[0]))
        elif name == "adx" and len(args) >= 1:
            features[ref] = fc.adx(bars["high"], bars["low"], bars["close"], int(args[0]))
        elif name == "bollinger" and len(args) >= 2:
            features[ref] = fc.bollinger(bars["close"], int(args[0]), float(args[1]))
        elif name == "macd" and len(args) >= 3:
            features[ref] = fc.macd(bars["close"], int(args[0]), int(args[1]), int(args[2]))
        elif name == "stochastic" and len(args) >= 1:
            features[ref] = fc.stochastic(bars["high"], bars["low"], bars["close"], int(args[0]))
        elif name == "realized_vol" and len(args) >= 1:
            features[ref] = fc.realized_vol(bars["close"], int(args[0]))
        elif name == "zscore" and len(args) >= 1:
            features[ref] = fc.zscore(bars["close"], int(args[0]))
        elif name == "rolling_high" and len(args) >= 1:
            features[ref] = fc.rolling_high(bars["high"], int(args[0]))
        elif name == "rolling_low" and len(args) >= 1:
            features[ref] = fc.rolling_low(bars["low"], int(args[0]))
        elif name == "avg_volume" and len(args) >= 1:
            features[ref] = fc.avg_volume(bars["volume"], int(args[0]))
        elif name == "range_detect" and len(args) >= 1:
            features[ref] = fc.range_detect(bars["high"], bars["low"], int(args[0]))
        elif name == "vwap":
            w = int(args[0]) if args else None
            features[ref] = fc.vwap(bars["close"], bars["volume"], w)
        elif name == "dollar_volume":
            features[ref] = fc.dollar_volume(bars["close"], bars["volume"])

    return features


def _collect_refs(spec: StrategySpec) -> set[str]:
    """Walk the spec and collect all feature references."""
    refs: set[str] = set()
    _walk_collect(spec.regime, refs)
    _walk_collect(spec.entry, refs)
    for exit_ in spec.exits:
        _walk_collect(exit_, refs)
    return refs


def _walk_collect(obj: Any, refs: set[str]) -> None:
    if isinstance(obj, str):
        if "(" in obj and ")" in obj:
            refs.add(obj)
            # Also collect base for record-field access
            if "." in obj:
                base = obj.rsplit(".", 1)[0]
                refs.add(base)
    elif isinstance(obj, dict):
        for v in obj.values():
            _walk_collect(v, refs)
        if "expr" in obj:
            _walk_collect(obj["expr"], refs)
    elif isinstance(obj, list):
        for v in obj:
            _walk_collect(v, refs)


def _evaluate_condition(cond: Any, features: dict[str, Any], bars: pd.DataFrame) -> pd.Series:
    """Evaluate a single DSL condition to a boolean Series."""
    n = len(bars)
    true_series = pd.Series(True, index=bars.index)

    if not isinstance(cond, dict):
        return true_series

    for op, args in cond.items():
        if op == "gt" and isinstance(args, list) and len(args) == 2:
            a = _resolve_value(args[0], features, bars)
            b = _resolve_value(args[1], features, bars)
            return pd.Series(a > b, index=bars.index).fillna(False)
        elif op == "lt" and isinstance(args, list) and len(args) == 2:
            a = _resolve_value(args[0], features, bars)
            b = _resolve_value(args[1], features, bars)
            return pd.Series(a < b, index=bars.index).fillna(False)
        elif op == "between" and isinstance(args, list) and len(args) == 3:
            a = _resolve_value(args[0], features, bars)
            lo = _resolve_value(args[1], features, bars)
            hi = _resolve_value(args[2], features, bars)
            return pd.Series((a >= lo) & (a <= hi), index=bars.index).fillna(False)
        elif op == "within_band" and isinstance(args, list) and len(args) == 3:
            a = _resolve_value(args[0], features, bars)
            lo = _resolve_value(args[1], features, bars)
            hi = _resolve_value(args[2], features, bars)
            return pd.Series((a >= lo) & (a <= hi), index=bars.index).fillna(False)
        elif op == "outside_band" and isinstance(args, list) and len(args) == 3:
            a = _resolve_value(args[0], features, bars)
            lo = _resolve_value(args[1], features, bars)
            hi = _resolve_value(args[2], features, bars)
            return pd.Series((a < lo) | (a > hi), index=bars.index).fillna(False)
        elif op == "crosses_above" and isinstance(args, list) and len(args) == 2:
            a = _resolve_value(args[0], features, bars)
            b = _resolve_value(args[1], features, bars)
            a_s = pd.Series(a, index=bars.index) if not isinstance(a, pd.Series) else a
            b_s = pd.Series(b, index=bars.index) if not isinstance(b, pd.Series) else b
            return ((a_s > b_s) & (a_s.shift(1) <= b_s.shift(1))).fillna(False)
        elif op == "crosses_below" and isinstance(args, list) and len(args) == 2:
            a = _resolve_value(args[0], features, bars)
            b = _resolve_value(args[1], features, bars)
            a_s = pd.Series(a, index=bars.index) if not isinstance(a, pd.Series) else a
            b_s = pd.Series(b, index=bars.index) if not isinstance(b, pd.Series) else b
            return ((a_s < b_s) & (a_s.shift(1) >= b_s.shift(1))).fillna(False)
        elif op == "held_for" and isinstance(args, list) and len(args) == 2:
            inner = _evaluate_condition(args[0], features, bars)
            n_bars = int(args[1]) if isinstance(args[1], (int, float)) else int(_resolve_value(args[1], features, bars))
            return inner.rolling(window=n_bars).min().fillna(0).astype(bool)
        elif op == "all_of" and isinstance(args, list):
            result = true_series.copy()
            for sub in args:
                result = result & _evaluate_condition(sub, features, bars)
            return result
        elif op == "any_of" and isinstance(args, list):
            result = pd.Series(False, index=bars.index)
            for sub in args:
                result = result | _evaluate_condition(sub, features, bars)
            return result
        elif op == "not" and isinstance(args, (dict, list)):
            inner = _evaluate_condition(args[0] if isinstance(args, list) else args, features, bars)
            return ~inner

    return true_series


def _evaluate_regime(regime: dict, features: dict[str, Any], bars: pd.DataFrame) -> pd.Series:
    """Evaluate regime.all_of conditions."""
    all_of = regime.get("all_of", [])
    if not all_of:
        return pd.Series(True, index=bars.index)

    result = pd.Series(True, index=bars.index)
    for cond in all_of:
        result = result & _evaluate_condition(cond, features, bars)
    return result.fillna(False)


def _evaluate_entry(entry: dict, features: dict[str, Any], bars: pd.DataFrame) -> pd.Series:
    """Evaluate entry.when condition."""
    when = entry.get("when", {})
    if not when:
        return pd.Series(False, index=bars.index)
    return _evaluate_condition(when, features, bars).fillna(False)


def _entry_direction(entry: dict) -> int:
    """Return 1 for long, -1 for short."""
    action = entry.get("action", "enter_long")
    return -1 if action == "enter_short" else 1


def _compute_exits(
    spec: StrategySpec, bars: pd.DataFrame, features: dict[str, Any], result: pd.DataFrame
) -> None:
    """Compute stop-loss and take-profit levels per bar."""
    for exit_spec in spec.exits:
        if "stop_loss" in exit_spec:
            sl = exit_spec["stop_loss"]
            if "atr_mult" in sl:
                mult = sl["atr_mult"]
                atr_ref = sl.get("ref")
                if atr_ref:
                    ref_val = _resolve_value(atr_ref, features, bars)
                else:
                    from app.modules.data.features import FeatureComputer as fc
                    ref_val = bars["close"]
                atr_val = features.get("atr(14)")
                if atr_val is None:
                    from app.modules.data.features import FeatureComputer as fc
                    atr_val = fc.atr(bars["high"], bars["low"], bars["close"], 14)
                direction = _entry_direction(spec.entry)
                if direction == 1:
                    result["stop_loss"] = bars["close"] - mult * atr_val
                else:
                    result["stop_loss"] = bars["close"] + mult * atr_val
            elif "pct" in sl:
                pct = sl["pct"] / 100.0
                direction = _entry_direction(spec.entry)
                if direction == 1:
                    result["stop_loss"] = bars["close"] * (1 - pct)
                else:
                    result["stop_loss"] = bars["close"] * (1 + pct)

        if "take_profit" in exit_spec:
            tp = exit_spec["take_profit"]
            if "ref" in tp:
                result["take_profit"] = _resolve_value(tp["ref"], features, bars)
            elif "pct" in tp:
                pct = tp["pct"] / 100.0
                direction = _entry_direction(spec.entry)
                if direction == 1:
                    result["take_profit"] = bars["close"] * (1 + pct)
                else:
                    result["take_profit"] = bars["close"] * (1 - pct)
            elif "atr_mult" in tp:
                mult = tp["atr_mult"]
                atr_val = features.get("atr(14)")
                if atr_val is None:
                    from app.modules.data.features import FeatureComputer as fc
                    atr_val = fc.atr(bars["high"], bars["low"], bars["close"], 14)
                direction = _entry_direction(spec.entry)
                if direction == 1:
                    result["take_profit"] = bars["close"] + mult * atr_val
                else:
                    result["take_profit"] = bars["close"] - mult * atr_val


def _compute_sizing(
    spec: StrategySpec, bars: pd.DataFrame, features: dict[str, Any], result: pd.DataFrame
) -> None:
    """Compute position sizing per bar."""
    sizing = spec.entry.get("sizing", {})
    if "fixed_pct" in sizing:
        pct = sizing["fixed_pct"]["pct"]
        result["position_size_pct"] = np.where(result["signal"] != 0, pct, 0.0)
    elif "vol_scaled" in sizing:
        target_vol = sizing["vol_scaled"]["target_vol"]
        vol = features.get("realized_vol(20)")
        if vol is None:
            from app.modules.data.features import FeatureComputer as fc
            vol = fc.realized_vol(bars["close"], 20)
        scaled = target_vol / vol.replace(0, np.inf)
        scaled = scaled.clip(upper=spec.risk.max_position_pct)
        result["position_size_pct"] = np.where(result["signal"] != 0, scaled, 0.0)
    else:
        result["position_size_pct"] = np.where(
            result["signal"] != 0, spec.risk.max_position_pct, 0.0
        )
