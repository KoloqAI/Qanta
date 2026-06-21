from __future__ import annotations

from fastapi import APIRouter

from app.deps import DB, CurrentUser

router = APIRouter()


@router.get("")
async def get_portfolio(db: DB, user: CurrentUser) -> dict:
    return {
        "equity": 100_000,
        "day_pnl": 0,
        "period_return": 0,
        "sharpe": 0,
        "max_dd": 0,
        "win_rate": 0,
        "equity_curve": [],
        "deployments": [],
        "allocation": [],
    }
