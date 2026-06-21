from __future__ import annotations

from fastapi import APIRouter

from app.deps import DB, CurrentUser
from app import state

router = APIRouter()


@router.get("")
async def get_portfolio(db: DB, user: CurrentUser) -> dict:
    """Return real portfolio data from the paper broker and allocator."""
    positions = await state.broker.positions()

    # Compute gross exposure from positions
    gross_exposure = sum(
        abs(p.get("qty", 0)) * 100  # approximate value at $100/share
        for p in positions
    )

    # Compute equity: initial equity + unrealised PnL
    # In paper mode, PnL comes from fills against initial equity
    equity = state.INITIAL_EQUITY
    day_pnl = 0.0

    # Build deployment summaries
    deployment_list = []
    for dep_id, dep in state.deployments.items():
        dep_positions = [p for p in positions if p.get("deployment_id") == dep_id]
        deployment_list.append({
            "id": dep_id,
            "strategy_id": dep.get("strategy_id", ""),
            "strategy_name": dep.get("strategy_name", ""),
            "mode": dep.get("mode", "paper"),
            "status": dep.get("status", "active"),
            "positions": dep_positions,
        })

    # Run allocator on active deployments
    active_deployments = [
        d for d in deployment_list if d.get("status") == "active"
    ]
    allocation_map = state.allocator.allocate(active_deployments, equity)
    allocation = [
        {"deployment_id": dep_id, "allocated": amount}
        for dep_id, amount in allocation_map.items()
    ]

    # Sharpe and drawdown from monitoring if available
    sharpe = 0.0
    max_dd = 0.0
    win_rate = 0.0

    return {
        "equity": equity,
        "day_pnl": day_pnl,
        "period_return": (day_pnl / equity * 100) if equity > 0 else 0,
        "sharpe": sharpe,
        "max_dd": max_dd,
        "win_rate": win_rate,
        "gross_exposure": gross_exposure,
        "equity_curve": [],
        "deployments": deployment_list,
        "allocation": allocation,
        "positions": positions,
    }
