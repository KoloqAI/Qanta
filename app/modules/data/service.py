from __future__ import annotations

from datetime import datetime
from typing import Protocol

import pandas as pd


class MarketDataProvider(Protocol):
    async def bars(
        self,
        symbol: str,
        start: datetime,
        end: datetime,
        timeframe: str,
        as_of: datetime | None = None,
    ) -> pd.DataFrame: ...

    async def universe(self, as_of: datetime | None = None) -> list[str]: ...


class FeatureStore(Protocol):
    async def compute_features(
        self, symbol: str, bars: pd.DataFrame, features: list[str]
    ) -> pd.DataFrame: ...

    async def get_corporate_actions(
        self, symbol: str, start: datetime, end: datetime
    ) -> list[dict]: ...
