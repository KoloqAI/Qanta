from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class ArchetypeResponse(BaseModel):
    id: str
    name: str
    family: str
    horizon: str
    thesis: str
    status: str
    source: str

    model_config = {"from_attributes": True}


class ArchetypeDetail(ArchetypeResponse):
    template: dict[str, Any]
    scan: dict[str, Any]
    param_grid: dict[str, Any]
    exploration_funnel: dict[str, Any] | None = None


class ScanBody(BaseModel):
    universe: list[str] | None = None
    as_of: str | None = None


class ScanResult(BaseModel):
    archetype_id: str
    candidates: list[dict[str, Any]]


class ExploreBody(BaseModel):
    budget: int = 10
    param_grid: dict[str, Any] | None = None


class BacktestBody(BaseModel):
    source: dict[str, Any]
    tickers: list[str]
    start: str
    end: str
    timeframe: str = "1d"
    mode: str = "backtest_only"
