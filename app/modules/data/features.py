from __future__ import annotations

import re
import logging

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

_FEATURE_PATTERN = re.compile(r"^(\w+)(?:\(([^)]*)\))?(?:\.(\w+))?$")


class FeatureComputer:
    """Computes DSL feature primitives from OHLCV bars."""

    @staticmethod
    def sma(series: pd.Series, n: int) -> pd.Series:
        return series.rolling(window=n).mean()

    @staticmethod
    def ema(series: pd.Series, n: int) -> pd.Series:
        return series.ewm(span=n, adjust=False).mean()

    @staticmethod
    def rsi(series: pd.Series, n: int) -> pd.Series:
        delta = series.diff()
        gain = delta.where(delta > 0, 0.0)
        loss = -delta.where(delta < 0, 0.0)
        avg_gain = gain.ewm(alpha=1 / n, min_periods=n, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1 / n, min_periods=n, adjust=False).mean()
        rs = avg_gain / avg_loss.replace(0, np.inf)
        return 100.0 - (100.0 / (1.0 + rs))

    @staticmethod
    def atr(high: pd.Series, low: pd.Series, close: pd.Series, n: int) -> pd.Series:
        prev_close = close.shift(1)
        tr = pd.concat([
            high - low,
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ], axis=1).max(axis=1)
        return tr.ewm(span=n, adjust=False).mean()

    @staticmethod
    def bollinger(series: pd.Series, n: int, k: float) -> dict[str, pd.Series]:
        mid = series.rolling(window=n).mean()
        std = series.rolling(window=n).std()
        return {"mid": mid, "upper": mid + k * std, "lower": mid - k * std}

    @staticmethod
    def macd(series: pd.Series, fast: int, slow: int, signal: int) -> dict[str, pd.Series]:
        ema_fast = series.ewm(span=fast, adjust=False).mean()
        ema_slow = series.ewm(span=slow, adjust=False).mean()
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal, adjust=False).mean()
        hist = macd_line - signal_line
        return {"macd": macd_line, "signal": signal_line, "hist": hist}

    @staticmethod
    def adx(high: pd.Series, low: pd.Series, close: pd.Series, n: int) -> pd.Series:
        plus_dm = high.diff()
        minus_dm = -low.diff()
        plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0.0)
        minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0.0)

        atr_val = FeatureComputer.atr(high, low, close, n)
        plus_di = 100 * (plus_dm.ewm(span=n, adjust=False).mean() / atr_val)
        minus_di = 100 * (minus_dm.ewm(span=n, adjust=False).mean() / atr_val)
        dx = 100 * ((plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.inf))
        return dx.ewm(span=n, adjust=False).mean()

    @staticmethod
    def stochastic(high: pd.Series, low: pd.Series, close: pd.Series, n: int) -> dict[str, pd.Series]:
        lowest_low = low.rolling(window=n).min()
        highest_high = high.rolling(window=n).max()
        k = 100 * (close - lowest_low) / (highest_high - lowest_low).replace(0, np.inf)
        d = k.rolling(window=3).mean()
        return {"k": k, "d": d}

    @staticmethod
    def realized_vol(series: pd.Series, n: int) -> pd.Series:
        log_returns = np.log(series / series.shift(1))
        return log_returns.rolling(window=n).std() * np.sqrt(252)

    @staticmethod
    def zscore(series: pd.Series, n: int) -> pd.Series:
        mean = series.rolling(window=n).mean()
        std = series.rolling(window=n).std()
        return (series - mean) / std.replace(0, np.inf)

    @staticmethod
    def rolling_high(series: pd.Series, n: int) -> pd.Series:
        return series.rolling(window=n).max()

    @staticmethod
    def rolling_low(series: pd.Series, n: int) -> pd.Series:
        return series.rolling(window=n).min()

    @staticmethod
    def avg_volume(volume: pd.Series, n: int) -> pd.Series:
        return volume.rolling(window=n).mean()

    @staticmethod
    def vwap(close: pd.Series, volume: pd.Series, window: int | None = None) -> pd.Series:
        if window is None:
            return (close * volume).cumsum() / volume.cumsum()
        return (close * volume).rolling(window).sum() / volume.rolling(window).sum()

    @staticmethod
    def dollar_volume(close: pd.Series, volume: pd.Series) -> pd.Series:
        return close * volume

    @staticmethod
    def range_detect(high: pd.Series, low: pd.Series, n: int) -> dict[str, pd.Series]:
        range_high = high.rolling(window=n).max()
        range_low = low.rolling(window=n).min()
        close_approx = (high + low) / 2
        in_range = (close_approx >= range_low) & (close_approx <= range_high)
        return {"high": range_high, "low": range_low, "in_range": in_range}


# ---------------------------------------------------------------------------
# DSL feature evaluation for scan conditions
# ---------------------------------------------------------------------------


def compute_dsl_feature(
    expr: str, bars: pd.DataFrame
) -> pd.Series | float | dict[str, pd.Series]:
    """Evaluate a DSL feature expression against OHLCV bars.

    Supports: ``rsi(14)``, ``sma(20)``, ``avg_volume(20)``, ``close``,
    ``bollinger(20,2).lower``, ``range_detect(20).in_range``, etc.
    """
    if expr in ("close", "open", "high", "low", "volume"):
        return bars[expr]

    match = _FEATURE_PATTERN.match(expr)
    if not match:
        raise ValueError(f"Unparseable DSL feature: {expr}")

    name, args_str, field = match.groups()
    args = [a.strip() for a in args_str.split(",")] if args_str else []

    fc = FeatureComputer
    result: pd.Series | dict[str, pd.Series]

    if name == "sma":
        result = fc.sma(bars["close"], int(args[0]))
    elif name == "ema":
        result = fc.ema(bars["close"], int(args[0]))
    elif name == "rsi":
        result = fc.rsi(bars["close"], int(args[0]))
    elif name == "atr":
        result = fc.atr(bars["high"], bars["low"], bars["close"], int(args[0]))
    elif name == "avg_volume":
        result = fc.avg_volume(bars["volume"], int(args[0]))
    elif name == "realized_vol":
        result = fc.realized_vol(bars["close"], int(args[0]))
    elif name == "zscore":
        result = fc.zscore(bars["close"], int(args[0]))
    elif name == "adx":
        result = fc.adx(bars["high"], bars["low"], bars["close"], int(args[0]))
    elif name == "rolling_high":
        result = fc.rolling_high(bars["close"], int(args[0]))
    elif name == "rolling_low":
        result = fc.rolling_low(bars["low"], int(args[0]))
    elif name == "dollar_volume":
        result = fc.dollar_volume(bars["close"], bars["volume"])
    elif name == "vwap":
        w = int(args[0]) if args else None
        result = fc.vwap(bars["close"], bars["volume"], w)
    elif name == "bollinger":
        result = fc.bollinger(bars["close"], int(args[0]), float(args[1]))
    elif name == "macd":
        result = fc.macd(bars["close"], int(args[0]), int(args[1]), int(args[2]))
    elif name == "stochastic":
        result = fc.stochastic(
            bars["high"], bars["low"], bars["close"], int(args[0])
        )
    elif name == "range_detect":
        result = fc.range_detect(bars["high"], bars["low"], int(args[0]))
    else:
        raise ValueError(f"Unknown DSL feature: {name}")

    if isinstance(result, dict):
        if field:
            return result[field]
        raise ValueError(
            f"Feature '{name}' returns multiple series; specify .field"
        )
    return result


def _resolve_operand(operand: object, bars: pd.DataFrame) -> float:
    """Resolve a scan condition operand to the last non-NaN scalar."""
    if isinstance(operand, (int, float)):
        return float(operand)
    if isinstance(operand, str):
        series = compute_dsl_feature(operand, bars)
        if isinstance(series, pd.Series):
            clean = series.dropna()
            if clean.empty:
                return float("nan")
            return float(clean.iloc[-1])
        return float(series)
    if isinstance(operand, dict) and "expr" in operand:
        raise ValueError(f"Complex expressions not yet supported: {operand}")
    raise ValueError(f"Unknown operand type: {operand}")


def evaluate_condition(
    condition: dict, bars: pd.DataFrame
) -> tuple[bool, float]:
    """Evaluate one scan condition.  Returns ``(passed, score)``."""
    for op, operands in condition.items():
        if op == "gt":
            left = _resolve_operand(operands[0], bars)
            right = _resolve_operand(operands[1], bars)
            if np.isnan(left) or np.isnan(right):
                return False, 0.0
            if left <= right:
                return False, 0.0
            score = min(1.0, (left - right) / max(abs(right), 1e-9))
            return True, score

        if op == "lt":
            left = _resolve_operand(operands[0], bars)
            right = _resolve_operand(operands[1], bars)
            if np.isnan(left) or np.isnan(right):
                return False, 0.0
            if left >= right:
                return False, 0.0
            score = min(1.0, (right - left) / max(abs(right), 1e-9))
            return True, score

        if op == "between":
            val = _resolve_operand(operands[0], bars)
            low = _resolve_operand(operands[1], bars)
            high = _resolve_operand(operands[2], bars)
            if any(np.isnan(v) for v in (val, low, high)):
                return False, 0.0
            if not (low <= val <= high):
                return False, 0.0
            mid = (low + high) / 2
            half = (high - low) / 2
            score = 1.0 - abs(val - mid) / max(half, 1e-9)
            return True, max(0.0, score)

        if op in ("crosses_above", "crosses_below"):
            left_s = compute_dsl_feature(operands[0], bars)
            right_s = compute_dsl_feature(operands[1], bars)
            if not (
                isinstance(left_s, pd.Series) and isinstance(right_s, pd.Series)
            ):
                return False, 0.0
            if len(left_s) < 2 or len(right_s) < 2:
                return False, 0.0
            prev_l, curr_l = float(left_s.iloc[-2]), float(left_s.iloc[-1])
            prev_r, curr_r = float(right_s.iloc[-2]), float(right_s.iloc[-1])
            if op == "crosses_above":
                crossed = prev_l <= prev_r and curr_l > curr_r
            else:
                crossed = prev_l >= prev_r and curr_l < curr_r
            return (True, 0.8) if crossed else (False, 0.0)

        # Boolean assertion: ``{range_detect(20).in_range: true}``
        if isinstance(operands, bool):
            series = compute_dsl_feature(op, bars)
            if isinstance(series, pd.Series) and not series.empty:
                val = bool(series.iloc[-1])
                return (True, 0.7) if val == operands else (False, 0.0)
            return False, 0.0

        return False, 0.0

    return False, 0.0


def evaluate_scan_block(scan_block: dict, bars: pd.DataFrame) -> float:
    """Evaluate all conditions in a scan block.

    Returns a fit score in ``(0, 1]`` if all conditions pass, ``0`` otherwise.
    An empty scan block yields a neutral ``0.5``.
    """
    if not scan_block:
        return 0.5

    all_of = scan_block.get("all_of", [])
    any_of = scan_block.get("any_of", [])

    if not all_of and not any_of:
        return 0.5

    scores: list[float] = []

    for cond in all_of:
        passed, score = evaluate_condition(cond, bars)
        if not passed:
            return 0.0
        scores.append(score)

    if any_of:
        best = 0.0
        any_passed = False
        for cond in any_of:
            passed, score = evaluate_condition(cond, bars)
            if passed:
                any_passed = True
                best = max(best, score)
        if not any_passed:
            return 0.0
        scores.append(best)

    return sum(scores) / len(scores) if scores else 0.5
