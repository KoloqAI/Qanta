from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class AppearanceSettings(BaseModel):
    theme: str = "system"


class RiskSettings(BaseModel):
    per_trade_stop_pct: float
    max_position_pct: float
    max_gross_exposure_pct: float
    daily_drawdown_kill_pct: float


class ConnectionsSettings(BaseModel):
    broker: dict[str, Any] = {}
    data: dict[str, Any] = {}


class ModelSettings(BaseModel):
    tiers: dict[str, Any] = {}
