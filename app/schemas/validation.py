from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class ValidationReportResponse(BaseModel):
    id: str
    deflated_sharpe: float
    pbo: float
    deg_slope: float
    peer_hit: float
    n_eff: int
    passed: bool
    confidence_curve: list[dict[str, Any]] | None
    detail: dict[str, Any] | None

    model_config = {"from_attributes": True}


class ConfidenceResponse(BaseModel):
    C: float
    C_lo: float
    C_hi: float
    regime_held_pct: float
    peer_hit: str
    dsr: float
    pbo: float
    headline: str
