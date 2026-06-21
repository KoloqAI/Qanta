from __future__ import annotations

from fastapi import APIRouter

from app.deps import DB, CurrentUser

router = APIRouter()


@router.get("")
async def get_monitor(db: DB, user: CurrentUser) -> dict:
    return {
        "account_pnl": 0,
        "gross_exposure": 0,
        "kill_switch": False,
        "deployments": [],
    }
