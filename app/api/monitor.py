from __future__ import annotations

from fastapi import APIRouter

from app.deps import DB, CurrentUser
from app import state

router = APIRouter()


@router.get("")
async def get_monitor(db: DB, user: CurrentUser) -> dict:
    """Return real-time monitoring data from the paper broker and risk gate."""
    positions = await state.broker.positions()

    # Compute gross exposure
    gross_exposure = sum(
        abs(p.get("qty", 0)) * 100  # approximate value at $100/share
        for p in positions
    )

    # Account PnL (paper mode -- starts at zero)
    account_pnl = 0.0

    # Kill switch status from risk gate
    kill_switch = state.risk_gate.is_killed

    # Build deployment monitoring view
    deployment_monitors = []
    for dep_id, dep in state.deployments.items():
        dep_positions = [p for p in positions if p.get("deployment_id") == dep_id]
        runtime_active = dep_id in state.runtime._active

        # Check for performance decay
        decay_info = await state.monitoring.check_decay(dep_id)

        guardrail_health = "ok"
        if kill_switch:
            guardrail_health = "critical"
        elif decay_info.get("decayed"):
            guardrail_health = "warning"

        deployment_monitors.append({
            "id": dep_id,
            "name": dep.get("strategy_name", "Untitled"),
            "strategy_id": dep.get("strategy_id", ""),
            "mode": dep.get("mode", "paper"),
            "status": dep.get("status", "active"),
            "runtime_active": runtime_active,
            "positions": dep_positions,
            "pnl": dep.get("pnl", 0.0),
            "guardrail_health": guardrail_health,
            "decay": decay_info,
        })

    return {
        "account_pnl": account_pnl,
        "gross_exposure": gross_exposure,
        "kill_switch": kill_switch,
        "equity": state.INITIAL_EQUITY,
        "positions": positions,
        "deployments": deployment_monitors,
    }
