from __future__ import annotations

import hashlib
import logging
from datetime import datetime, date, timedelta
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


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


# Polygon aggregate timespans keyed by the suffix of our timeframe strings.
_POLYGON_TIMESPAN = {
    "m": "minute",
    "h": "hour",
    "d": "day",
    "w": "week",
}


def _parse_timeframe(timeframe: str) -> tuple[int, str]:
    """Convert a timeframe like ``"1d"`` / ``"15m"`` into Polygon
    ``(multiplier, timespan)``.  Defaults to one-day bars on anything unknown."""
    tf = (timeframe or "1d").strip().lower()
    unit = tf[-1]
    timespan = _POLYGON_TIMESPAN.get(unit)
    if timespan is None:
        return 1, "day"
    try:
        multiplier = int(tf[:-1] or "1")
    except ValueError:
        multiplier = 1
    return max(multiplier, 1), timespan


class PolygonDataProvider:
    """Market data backed by the Polygon.io REST API.

    Produces the same DataFrame shape as :class:`SampleDataProvider`
    (``open/high/low/close/volume`` columns indexed by a ``date`` index) so all
    downstream feature/backtest code is provider-agnostic.

    Read-only: this provider only fetches market data and never touches the
    execution path.
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.polygon.io",
        timeout: float = 30.0,
    ) -> None:
        if not api_key:
            raise ValueError("PolygonDataProvider requires a non-empty api_key")
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    async def bars(
        self,
        symbol: str,
        start: datetime,
        end: datetime,
        timeframe: str = "1d",
        as_of: datetime | None = None,
    ) -> pd.DataFrame:
        # Point-in-time guard: never return bars dated after as_of.
        if as_of is not None and end > as_of:
            end = as_of
        if start > end:
            return _empty_bars()

        multiplier, timespan = _parse_timeframe(timeframe)
        path = (
            f"/v2/aggs/ticker/{symbol.upper()}/range/{multiplier}/{timespan}"
            f"/{start.date().isoformat()}/{end.date().isoformat()}"
        )
        params = {
            "adjusted": "true",
            "sort": "asc",
            "limit": 50000,
            "apiKey": self._api_key,
        }

        import httpx

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.get(f"{self._base_url}{path}", params=params)

        if resp.status_code == 401:
            raise RuntimeError("Polygon authentication failed — check POLYGON_API_KEY")
        if resp.status_code == 429:
            raise RuntimeError("Polygon rate limit exceeded — retry later or upgrade plan")
        resp.raise_for_status()

        payload = resp.json()
        results = payload.get("results") or []
        if not results:
            logger.info(
                "Polygon returned no bars for %s (%s → %s, %s)",
                symbol, start.date(), end.date(), timeframe,
            )
            return _empty_bars()

        df = pd.DataFrame(results)
        # Polygon fields: t=ms epoch (UTC), o/h/l/c=OHLC, v=volume.
        df["date"] = pd.to_datetime(df["t"], unit="ms", utc=True).dt.tz_localize(None)
        df = (
            df.rename(columns={"o": "open", "h": "high", "l": "low", "c": "close", "v": "volume"})
            [["date", "open", "high", "low", "close", "volume"]]
            .set_index("date")
            .sort_index()
        )
        df[["open", "high", "low", "close"]] = df[["open", "high", "low", "close"]].astype(float)
        df["volume"] = df["volume"].astype(float)
        df.index.name = "date"
        return df

    async def universe(self, as_of: datetime | None = None) -> list[str]:
        """Return a curated set of liquid US large-caps as the scan universe.

        Polygon's full ticker reference contains thousands of symbols, which is
        not a useful default for a research scan, so we reuse the curated
        large-cap list (all real, tradeable tickers).
        """
        return sorted(SAMPLE_UNIVERSE)


def _empty_bars() -> pd.DataFrame:
    df = pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
    df.index.name = "date"
    return df


def recent_window(lookback_days: int) -> tuple[datetime, datetime]:
    """Return a ``(start, end)`` window ending ~yesterday and spanning
    ``lookback_days``.

    Live-analysis and default backtest windows use this so requests fall inside
    a data provider's entitlement (e.g. Polygon's free tier ~2y history) while
    staying correct for current analysis. The synthetic SampleDataProvider is
    deterministic for any window, so this is safe across providers.
    """
    end = datetime.now() - timedelta(days=1)
    start = end - timedelta(days=lookback_days)
    return start, end


def create_data_provider() -> Any:
    """Return the configured market-data provider.

    Uses :class:`PolygonDataProvider` when ``POLYGON_API_KEY`` is set, otherwise
    falls back to the deterministic :class:`SampleDataProvider` so the platform
    runs fully offline during development.
    """
    from app.config import settings

    if settings.polygon_api_key:
        logger.info("Using PolygonDataProvider (POLYGON_API_KEY detected)")
        return PolygonDataProvider(
            api_key=settings.polygon_api_key,
            base_url=settings.polygon_base_url,
        )

    logger.info("No POLYGON_API_KEY configured — using SampleDataProvider")
    return SampleDataProvider()
