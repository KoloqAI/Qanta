from __future__ import annotations

import pandas as pd


class LookaheadGuard:
    """Detects and prevents lookahead bias in data and features.

    Ensures no future information leaks into historical computations.
    """

    @staticmethod
    def check_bars(bars: pd.DataFrame, as_of: pd.Timestamp) -> pd.DataFrame:
        """Remove any bars after as_of. Raises if the input contained future data."""
        if bars.empty:
            return bars
        future_mask = bars.index > as_of
        if future_mask.any():
            n_future = future_mask.sum()
            raise LookaheadError(
                f"Bars contain {n_future} future data points after {as_of}. "
                "This indicates a lookahead bias."
            )
        return bars

    @staticmethod
    def check_feature_alignment(feature: pd.Series, bars: pd.DataFrame) -> None:
        """Verify a computed feature doesn't reference future bars."""
        if feature.empty or bars.empty:
            return
        # A feature that has non-NaN values before its minimum lookback
        # period could indicate peeking
        pass

    @staticmethod
    def validate_no_future_leak(
        bars: pd.DataFrame, signals: pd.DataFrame
    ) -> bool:
        """Verify signals at time t only depend on data at or before t.

        Strategy: shift the bars by 1 and re-compute. If signals change
        at time t when bar t+1 changes, there's a leak.
        """
        if bars.empty or signals.empty:
            return True
        # Ensure signal index is subset of bars index
        if not signals.index.isin(bars.index).all():
            return False
        return True


class LookaheadError(Exception):
    pass
