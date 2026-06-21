from __future__ import annotations

from fastapi import APIRouter

from app.deps import DB, CurrentUser

router = APIRouter()


@router.get("")
async def get_performance(db: DB, user: CurrentUser) -> dict:
    return {
        "total_return": 0,
        "sharpe": 0,
        "win_rate": 0,
        "history": [],
        "strategies": [],
        "calibration": [],
    }
