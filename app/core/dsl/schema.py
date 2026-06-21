from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any

@dataclass
class RiskEnvelope:
    max_position_pct: float
    per_trade_stop_pct: float
    max_gross_exposure: float

@dataclass
class ValidationTarget:
    R: float  # target return
    H: int    # horizon in sessions

@dataclass
class StrategySpec:
    id: str
    version: int
    tickers: list[str]
    thesis: str
    regime: dict[str, Any]
    entry: dict[str, Any]
    exits: list[dict[str, Any]]
    risk: RiskEnvelope
    universe: dict[str, Any]
    validation: dict[str, Any]
    author: dict[str, str] = field(default_factory=dict)
    dsl_version: int = 1
