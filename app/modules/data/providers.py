from __future__ import annotations

import hashlib
from datetime import datetime, date, timedelta
from typing import Any

import numpy as np
import pandas as pd


SAMPLE_UNIVERSE = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "TSLA", "JPM",
    "V", "JNJ", "WMT", "PG", "MA", "UNH", "HD", "DIS", "BAC", "XOM",
    "KO", "PEP", "MDLZ", "GIS", "CSCO", "INTC", "AMD", "CRM",
]

# Symbols that "delisted" at certain dates (for survivorship-free testing)
DELISTED = {
    "DELIST1": date(2022, 6, 15),
    "DELIST2": date(2023, 3, 1),
}


def _seed_for_symbol(symbol: str) -> int:
    return int(hashlib.md5(symbol.encode()).hexdigest()[:8], 16)


class SampleDataProvider:
    """Generates deterministic synthetic OHLCV for testing.

    Point-in-time: bars() never returns data after as_of.
    Survivorship-free: universe() includes delisted names when as_of precedes their delist date.
    """

    def __init__(self, base_price: float = 100.0, annual_vol: float = 0.25) -> None:
        self._base_price = base_price
        self._annual_vol = annual_vol

    async def bars(
        self,
        symbol: str,
        start: datetime,
        end: datetime,
        timeframe: str = "1d",
        as_of: datetime | None = None,
    ) -> pd.DataFrame:
        if as_of is not None and end > as_of:
            end = as_of

        # Check if symbol is delisted and clamp end date
        if symbol in DELISTED:
            delist_dt = datetime.combine(DELISTED[symbol], datetime.min.time())
            if start >= delist_dt:
                return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
            if end > delist_dt:
                end = delist_dt

        dates = pd.bdate_range(start=start.date(), end=end.date())
        if len(dates) == 0:
            return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])

        rng = np.random.default_rng(_seed_for_symbol(symbol))
        n = len(dates)

        daily_vol = self._annual_vol / np.sqrt(252)
        drift = 0.0005  # small positive drift
        returns = rng.normal(drift, daily_vol, n)

        close = np.zeros(n)
        close[0] = self._base_price * (1 + rng.uniform(-0.3, 0.3))
        for i in range(1, n):
            close[i] = close[i - 1] * np.exp(returns[i])

        # Generate OHLV from close
        intraday_vol = rng.uniform(0.005, 0.02, n)
        high = close * (1 + np.abs(rng.normal(0, intraday_vol)))
        low = close * (1 - np.abs(rng.normal(0, intraday_vol)))
        open_ = low + (high - low) * rng.uniform(0.2, 0.8, n)
        volume = rng.integers(500_000, 10_000_000, n).astype(float)

        df = pd.DataFrame(
            {"open": open_, "high": high, "low": low, "close": close, "volume": volume},
            index=dates,
        )
        df.index.name = "date"
        return df

    async def universe(self, as_of: datetime | None = None) -> list[str]:
        symbols = list(SAMPLE_UNIVERSE)
        for sym, delist_date in DELISTED.items():
            if as_of is None or as_of.date() < delist_date:
                symbols.append(sym)
        return sorted(symbols)
