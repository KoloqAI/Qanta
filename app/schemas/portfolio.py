from __future__ import annotations

from pydantic import BaseModel


class AllocationItem(BaseModel):
    deployment_id: str
    strategy_name: str
    capital: float
    pnl: float
    weight_pct: float


class PortfolioResponse(BaseModel):
    equity: float
    day_pnl: float
    period_return: float
    live_sharpe: float | None
    max_drawdown: float | None
    win_rate: float | None
    gross_exposure: float
    allocations: list[AllocationItem]
