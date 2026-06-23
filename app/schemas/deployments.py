from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class DeploymentCreate(BaseModel):
    strategy_version_id: str
    mode: str = "paper"
    guardrails: dict[str, Any] | None = None
    capital_budget: float | None = None


class DeploymentResponse(BaseModel):
    id: str
    strategy_version_id: str
    mode: str
    status: str
    capital_budget: float | None
    started_at: str | None
    ended_at: str | None

    model_config = {"from_attributes": True}
