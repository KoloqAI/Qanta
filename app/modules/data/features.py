from __future__ import annotations

import numpy as np
import pandas as pd


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
