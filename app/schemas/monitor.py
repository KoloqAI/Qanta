from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class DeploymentCard(BaseModel):
    id: str
    strategy_name: str
    mode: str
    status: str
    pnl: float
    positions: list[dict[str, Any]]
    guardrail_health: dict[str, Any]


class MonitorResponse(BaseModel):
    deployments: list[DeploymentCard]
    kill_switch_active: bool
    data_feed_status: str
