"""Enrich OHLCV bars with event-calendar columns for the DSL interpreter.

Event columns are injected into the bars DataFrame before interpretation so
the interpreter remains pure: ``interpret(spec, bars) -> signals`` with no
side-channel data.  The same enriched bars feed backtest and live paths,
preserving parity.

Columns added (reconstitution):
  ``_is_index_add``   — 1.0 on dates where the symbol is a confirmed index
                        addition (from final list through effective date), 0.0 otherwise.
  ``_is_index_delete``— same for deletions.
  ``_days_to_<kind>_effective`` — business days until the next effective date
                        for events of the given kind visible at that bar's date.
                        NaN when no upcoming event is visible.

Columns added (earnings):
  ``_days_to_earnings`` — signed business-day distance to the nearest visible
                          earnings announcement.  Negative = event in the past
                          (e.g. -2 means two sessions ago), positive = future,
                          0 = today.  NaN when no visible event within the
                          lookback/lookahead window.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

import numpy as np
import pandas as pd


def enrich_bars_with_events(
    bars: pd.DataFrame,
    symbol: str,
    events: list[dict],
) -> pd.DataFrame:
    """Add event columns to *bars* in-place and return it.

    Parameters
    ----------
    bars : DataFrame
        OHLCV bars indexed by date.
    symbol : str
        The ticker whose bars these are.
    events : list[dict]
        Reconstitution events (already point-in-time filtered by the provider).
        Each dict has: symbol, index, action, preliminary_list_date,
        final_list_date, effective_date.
    """
    if bars.empty:
        return bars

    n = len(bars)
    is_add = np.zeros(n, dtype=float)
    is_delete = np.zeros(n, dtype=float)

    bar_dates = bars.index.date if hasattr(bars.index, "date") else bars.index

    for evt in events:
        if evt["symbol"] != symbol:
            continue

        final_d = _to_date(evt["final_list_date"])
        effective_d = _to_date(evt["effective_date"])
        action = evt["action"]

        for i, d in enumerate(bar_dates):
            bd = _to_date(d)
            if final_d <= bd <= effective_d:
                if action == "add":
                    is_add[i] = 1.0
                elif action == "delete":
                    is_delete[i] = 1.0

    bars["_is_index_add"] = is_add
    bars["_is_index_delete"] = is_delete

    _add_days_to_effective(bars, symbol, events, "russell_effective")

    return bars


def _add_days_to_effective(
    bars: pd.DataFrame,
    symbol: str,
    events: list[dict],
    kind: str,
) -> None:
    """Add ``_days_to_{kind}`` column: business days until next effective date."""
    n = len(bars)
    days_col = np.full(n, np.nan)

    symbol_events = [
        e for e in events
        if e["symbol"] == symbol
    ]
    if not symbol_events:
        bars[f"_days_to_{kind}"] = days_col
        return

    bar_dates = bars.index.date if hasattr(bars.index, "date") else bars.index

    for i, d in enumerate(bar_dates):
        bd = _to_date(d)
        best = None
        for evt in symbol_events:
            eff_d = _to_date(evt["effective_date"])
            final_d = _to_date(evt["final_list_date"])
            if final_d <= bd and eff_d >= bd:
                bdays = _business_days_between(bd, eff_d)
                if best is None or bdays < best:
                    best = bdays
        if best is not None:
            days_col[i] = float(best)

    bars[f"_days_to_{kind}"] = days_col


def _to_date(d: Any) -> date:
    if isinstance(d, datetime):
        return d.date()
    if isinstance(d, pd.Timestamp):
        return d.date()
    return d


def _business_days_between(start: date, end: date) -> int:
    """Count business days from start to end (inclusive of end, exclusive of start)."""
    if start >= end:
        return 0
    bdays = pd.bdate_range(start=start, end=end)
    return max(0, len(bdays) - 1)


def enrich_bars_with_earnings(
    bars: pd.DataFrame,
    symbol: str,
    events: list[dict],
) -> pd.DataFrame:
    """Add earnings-event columns to *bars* in-place and return it.

    Parameters
    ----------
    bars : DataFrame
        OHLCV bars indexed by date.
    symbol : str
        The ticker whose bars these are (events are already filtered by the
        provider, but we double-check).
    events : list[dict]
        Earnings events (already point-in-time filtered).  Each dict has:
        ``symbol``, ``announce_date`` (date), ``session`` (``BMO`` or ``AMC``).

    Columns produced
    ----------------
    ``_days_to_earnings`` : signed business-day distance to the nearest
        visible earnings announcement.  Negative = past, positive = future,
        0 = today.
    """
    if bars.empty:
        return bars

    n = len(bars)
    days_col = np.full(n, np.nan)

    bar_dates = bars.index.date if hasattr(bars.index, "date") else bars.index

    sym_events = [e for e in events if e["symbol"] == symbol]
    if not sym_events:
        bars["_days_to_earnings"] = days_col
        return bars

    announce_dates = sorted(set(_to_date(e["announce_date"]) for e in sym_events))

    for i, d in enumerate(bar_dates):
        bd = _to_date(d)
        best_dist: float | None = None

        for ad in announce_dates:
            if ad == bd:
                best_dist = 0.0
                break
            elif ad < bd:
                dist = -_business_days_between(ad, bd)
            else:
                dist = _business_days_between(bd, ad)

            if best_dist is None or abs(dist) < abs(best_dist):
                best_dist = float(dist)

        if best_dist is not None:
            days_col[i] = best_dist

    bars["_days_to_earnings"] = days_col
    return bars
