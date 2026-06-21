from __future__ import annotations

from fastapi import APIRouter

from app.deps import DB, CurrentUser
from app import state

router = APIRouter()


@router.get("")
async def get_performance(db: DB, user: CurrentUser) -> dict:
    """Return performance data from monitoring service and registry."""
    # Gather strategy-level performance
    strategies_perf = []
    all_strategies = await state.registry.list_all()
    for s in all_strategies:
        sid = s["id"]
        report = state.validation_reports.get(sid, {})
        strategies_perf.append({
            "id": sid,
            "name": s.get("name", "Untitled"),
            "status": s.get("status", "draft"),
            "sharpe": report.get("sharpe", 0),
            "net_edge": report.get("net_edge", 0),
            "n_trades": report.get("n_trades", 0),
            "win_rate": report.get("win_rate", 0),
            "max_dd": report.get("max_dd", 0),
        })

    # Aggregate calibration data across all strategies
    calibration: list[dict] = []
    for s in all_strategies:
        cal = await state.monitoring.get_calibration(s["id"])
        calibration.extend(cal)

    # Aggregate portfolio-level metrics
    total_return = 0.0
    sharpe = 0.0
    win_rate = 0.0

    # Performance history from monitoring records
    history: list[dict] = []
    for dep_id in state.deployments:
        records = state.monitoring._performance.get(dep_id, [])
        for r in records:
            history.append({
                "deployment_id": dep_id,
                "ts": r.get("ts", ""),
                "sharpe": r.get("sharpe", 0),
                "pnl": r.get("pnl", 0),
            })

    return {
        "total_return": total_return,
        "sharpe": sharpe,
        "win_rate": win_rate,
        "history": history,
        "strategies": strategies_perf,
        "calibration": calibration,
    }
