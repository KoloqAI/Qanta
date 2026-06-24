from __future__ import annotations

import asyncio
import hashlib
import logging
import time
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

# Deterministic synthetic reconstitution calendar for testing.
# Russell 2000 reconstitutes annually in late June. We model two years of events
# with adds/deletes at the small-cap boundary. Dates are historical-style:
#   preliminary_list_date ~3 weeks before effective, final_list_date ~1 week before.
_SAMPLE_RECONSTITUTION_EVENTS: list[dict] = [
    # 2023 Russell reconstitution
    {"symbol": "RECON_ADD1", "index": "russell_2000", "action": "add",
     "preliminary_list_date": date(2023, 6, 2), "final_list_date": date(2023, 6, 16),
     "effective_date": date(2023, 6, 23)},
    {"symbol": "RECON_ADD2", "index": "russell_2000", "action": "add",
     "preliminary_list_date": date(2023, 6, 2), "final_list_date": date(2023, 6, 16),
     "effective_date": date(2023, 6, 23)},
    {"symbol": "RECON_DEL1", "index": "russell_2000", "action": "delete",
     "preliminary_list_date": date(2023, 6, 2), "final_list_date": date(2023, 6, 16),
     "effective_date": date(2023, 6, 23)},
    # 2024 Russell reconstitution
    {"symbol": "RECON_ADD3", "index": "russell_2000", "action": "add",
     "preliminary_list_date": date(2024, 5, 31), "final_list_date": date(2024, 6, 14),
     "effective_date": date(2024, 6, 28)},
    {"symbol": "RECON_ADD4", "index": "russell_2000", "action": "add",
     "preliminary_list_date": date(2024, 5, 31), "final_list_date": date(2024, 6, 14),
     "effective_date": date(2024, 6, 28)},
    {"symbol": "RECON_DEL2", "index": "russell_2000", "action": "delete",
     "preliminary_list_date": date(2024, 5, 31), "final_list_date": date(2024, 6, 14),
     "effective_date": date(2024, 6, 28)},
    {"symbol": "DELIST1", "index": "russell_2000", "action": "delete",
     "preliminary_list_date": date(2024, 5, 31), "final_list_date": date(2024, 6, 14),
     "effective_date": date(2024, 6, 28)},
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

    async def filtered_universe(
        self,
        as_of: datetime,
        min_price: float = 5,
        min_dollar_volume: float = 5_000_000,
        cap: int = 500,
    ) -> list[str]:
        return await self.universe(as_of=as_of)

    async def reconstitution_events(
        self,
        index: str,
        as_of: datetime,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> list[dict]:
        """Return reconstitution events visible at as_of (point-in-time).

        An event is only revealed once ``as_of >= final_list_date``.  This
        prevents lookahead: the membership change is unknown before the
        final list is published.
        """
        as_of_d = as_of.date() if isinstance(as_of, datetime) else as_of
        start_d = start.date() if start else date(2000, 1, 1)
        end_d = end.date() if end else date(2099, 12, 31)

        results: list[dict] = []
        for evt in _SAMPLE_RECONSTITUTION_EVENTS:
            if evt["index"] != index:
                continue
            if evt["final_list_date"] > as_of_d:
                continue
            if evt["effective_date"] < start_d or evt["effective_date"] > end_d:
                continue
            results.append(dict(evt))
        return results


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


class _PolygonRateLimiter:
    """Simple async rate limiter (token-bucket per minute)."""

    def __init__(self, calls_per_minute: int = 5) -> None:
        self._interval = 60.0 / max(calls_per_minute, 1)
        self._lock = asyncio.Lock()
        self._last_call = 0.0

    async def acquire(self) -> None:
        async with self._lock:
            now = time.monotonic()
            wait = self._interval - (now - self._last_call)
            if wait > 0:
                await asyncio.sleep(wait)
            self._last_call = time.monotonic()


def _trading_dates(end_date: date, window: int) -> list[date]:
    """Return the last *window* business days up to and including *end_date*."""
    start = end_date - timedelta(days=int(window * 1.6) + 10)
    dates = pd.bdate_range(start=start, end=end_date)
    return [d.date() for d in dates[-window:]]


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

        from app.config import settings
        self._rate_limiter = _PolygonRateLimiter(settings.polygon_calls_per_minute)
        self._grouped_cache: dict[str, list[dict]] = {}
        self._bars_cache: dict[str, pd.DataFrame] = {}

    # ------------------------------------------------------------------
    # Bars (per-ticker OHLCV)
    # ------------------------------------------------------------------

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

        cache_key = (
            f"{symbol}:{start.date().isoformat()}:{end.date().isoformat()}:{timeframe}"
        )
        if cache_key in self._bars_cache:
            return self._bars_cache[cache_key]

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

        await self._rate_limiter.acquire()

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

        self._bars_cache[cache_key] = df
        return df

    # ------------------------------------------------------------------
    # Grouped daily (all US equities for one date)
    # ------------------------------------------------------------------

    async def grouped_daily(self, target_date: date) -> list[dict]:
        """Fetch one day's OHLCV for every US equity via Polygon grouped daily.

        Returns a list of dicts with keys ``T`` (ticker), ``o``, ``h``, ``l``,
        ``c``, ``v``.  Results are cached in-memory by date.
        """
        key = target_date.isoformat()
        if key in self._grouped_cache:
            return self._grouped_cache[key]

        await self._rate_limiter.acquire()

        path = f"/v2/aggs/grouped/locale/us/market/stocks/{key}"
        params = {"adjusted": "true", "apiKey": self._api_key}

        import httpx

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.get(f"{self._base_url}{path}", params=params)

        if resp.status_code == 401:
            raise RuntimeError("Polygon authentication failed — check POLYGON_API_KEY")
        if resp.status_code == 429:
            raise RuntimeError("Polygon rate limit exceeded — retry later or upgrade plan")
        resp.raise_for_status()

        results = resp.json().get("results") or []
        self._grouped_cache[key] = results
        return results

    # ------------------------------------------------------------------
    # Filtered universe (grouped daily → liquidity filter → cap)
    # ------------------------------------------------------------------

    async def filtered_universe(
        self,
        as_of: datetime,
        min_price: float = 5,
        min_dollar_volume: float = 5_000_000,
        cap: int = 500,
    ) -> list[str]:
        """Build a scan universe from Polygon grouped daily data.

        1. Fetch grouped daily for ``as_of`` date → price filter.
        2. Fetch trailing window → compute median dollar-volume → volume filter.
        3. Sort by dollar volume descending, cap at *cap*.
        """
        from app.config import settings

        as_of_date = as_of.date()
        window_dates = _trading_dates(as_of_date, settings.scan_liquidity_window)
        if as_of_date not in window_dates:
            window_dates.append(as_of_date)

        # Fetch grouped daily for each date in the trailing window
        all_data: dict[str, list[tuple[float, float]]] = {}
        latest_price: dict[str, float] = {}

        for d in window_dates:
            rows = await self.grouped_daily(d)
            is_latest = d == as_of_date
            for row in rows:
                ticker = row.get("T", "")
                close = row.get("c", 0)
                volume = row.get("v", 0)
                if not ticker or close <= 0 or volume <= 0:
                    continue
                all_data.setdefault(ticker, []).append((close, volume))
                if is_latest:
                    latest_price[ticker] = close

        # Price filter using as_of date's close
        filtered: list[tuple[str, float]] = []
        for ticker, days in all_data.items():
            price = latest_price.get(ticker, 0)
            if price < min_price:
                continue

            dollar_vols = sorted(c * v for c, v in days)
            median_dv = dollar_vols[len(dollar_vols) // 2] if dollar_vols else 0

            if median_dv < min_dollar_volume:
                continue

            filtered.append((ticker, median_dv))

        filtered.sort(key=lambda x: x[1], reverse=True)
        result = [t for t, _ in filtered[:cap]]
        logger.info(
            "Polygon filtered universe: %d tickers (from %d total, cap=%d)",
            len(result), len(all_data), cap,
        )
        return result

    async def universe(self, as_of: datetime | None = None) -> list[str]:
        """Return a curated set of liquid US large-caps as the scan universe.

        When ``filtered_universe`` is used for scans this is kept for
        backwards-compat (backtest, research domain, etc.).
        """
        return sorted(SAMPLE_UNIVERSE)

    async def reconstitution_events(
        self,
        index: str,
        as_of: datetime,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> list[dict]:
        """Polygon does not provide index reconstitution data.

        A separate vendor feed (FTSE Russell, ICE, or a data vendor carrying
        index membership changes) must be wired.  This method raises so callers
        know the data path is not yet available.
        """
        raise NotImplementedError(
            "Reconstitution calendar requires a dedicated data feed "
            "(FTSE Russell / ICE / vendor). Polygon OHLCV does not include "
            "index membership changes. Wire a reconstitution provider or "
            "use SampleDataProvider for testing."
        )


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


# ---------------------------------------------------------------------------
# Event enrichment
# ---------------------------------------------------------------------------

EVENT_FEATURES = frozenset({"is_index_add", "is_index_delete", "days_to_event"})


def _needs_event_enrichment(archetype: dict) -> bool:
    """Check if an archetype references event features in watches, scan, or template."""
    import json as _json

    watches = archetype.get("watches", [])
    if any(w in EVENT_FEATURES for w in watches):
        return True
    combined = _json.dumps(archetype.get("scan", {})) + _json.dumps(archetype.get("template", {}))
    return any(feat in combined for feat in EVENT_FEATURES)


async def enrich_bars_if_needed(
    provider: Any,
    archetype: dict,
    ticker: str,
    bars: pd.DataFrame,
    as_of: datetime,
) -> pd.DataFrame:
    """Enrich bars with event columns when the archetype references event features."""
    if bars.empty or not _needs_event_enrichment(archetype):
        return bars

    from app.modules.data.events import enrich_bars_with_events

    try:
        events = await provider.reconstitution_events(
            index="russell_2000", as_of=as_of,
        )
    except (NotImplementedError, AttributeError):
        events = []

    if events:
        enrich_bars_with_events(bars, ticker, events)
    return bars


# ---------------------------------------------------------------------------
# Scan orchestration
# ---------------------------------------------------------------------------


async def scan_universe(
    archetype: dict,
    as_of: datetime | None = None,
) -> dict:
    """Build a filtered universe, evaluate scan conditions, return ranked candidates.

    Pipeline:
      1. ``filtered_universe()`` — grouped daily → price/liquidity filter → cap
      2. Short-circuit cheap conditions using grouped-daily data where possible
      3. Fetch full bar history for survivors → evaluate all DSL scan conditions
      4. Rank by fit score and return

    Returns ``{"candidates": [...], "is_sample_fallback": bool}``.
    """
    from app.config import settings
    from app.modules.data.features import evaluate_scan_block

    provider = create_data_provider()
    is_sample = isinstance(provider, SampleDataProvider)

    scan_block = archetype.get("scan", {})
    default_univ = archetype.get("default_universe", {})
    min_price = default_univ.get("min_price", 5)
    min_dollar_vol = default_univ.get("min_dollar_volume", 5_000_000)

    if as_of is None:
        as_of = datetime.now() - timedelta(days=1)

    tickers = await provider.filtered_universe(
        as_of=as_of,
        min_price=min_price,
        min_dollar_volume=min_dollar_vol,
        cap=settings.scan_universe_cap,
    )

    lookback = timedelta(days=settings.scan_bar_lookback_days)
    start = as_of - lookback
    archetype_name = archetype.get("name", "")
    archetype_family = archetype.get("family", "")

    sem = asyncio.Semaphore(10)

    needs_events = _needs_event_enrichment(archetype)
    recon_events: list[dict] | None = None
    if needs_events:
        try:
            recon_events = await provider.reconstitution_events(
                index="russell_2000", as_of=as_of,
            )
        except (NotImplementedError, AttributeError):
            recon_events = []

    async def _evaluate(ticker: str) -> dict | None:
        async with sem:
            try:
                bars = await provider.bars(ticker, start, as_of, as_of=as_of)
            except Exception:
                logger.warning("Failed to fetch bars for %s — skipping", ticker)
                return None
            if bars.empty or len(bars) < 10:
                return None
            if recon_events is not None and recon_events:
                from app.modules.data.events import enrich_bars_with_events
                enrich_bars_with_events(bars, ticker, recon_events)
            try:
                score = evaluate_scan_block(scan_block, bars)
            except Exception:
                logger.debug("Scan eval error for %s — skipping", ticker, exc_info=True)
                return None
            if score <= 0:
                return None
            return {
                "ticker": ticker,
                "fit_score": round(score, 4),
                "archetype": archetype_name,
                "family": archetype_family,
            }

    results = await asyncio.gather(*[_evaluate(t) for t in tickers])
    candidates = [r for r in results if r is not None]
    candidates.sort(key=lambda c: c["fit_score"], reverse=True)

    logger.info(
        "Scan complete: %d/%d passed for archetype '%s'",
        len(candidates), len(tickers), archetype_name,
    )

    return {
        "candidates": candidates,
        "is_sample_fallback": is_sample,
    }
