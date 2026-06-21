from __future__ import annotations

from fastapi import APIRouter

from app.deps import DB, CurrentUser

router = APIRouter()


@router.get("")
async def list_strategies(db: DB, user: CurrentUser) -> list:
    # M3 Registry: filter by state/family/ticker
    return []


@router.get("/{strategy_id}")
async def get_strategy(strategy_id: str, db: DB, user: CurrentUser) -> dict:
    # M3 Registry: detail with versions, validation report, deployments
    return {"id": strategy_id}


@router.post("/{strategy_id}/validate")
async def validate_strategy(strategy_id: str, db: DB, user: CurrentUser) -> dict:
    # M5 Validation: run the gauntlet -> job_id
    return {"job_id": "stub"}


@router.post("/{strategy_id}/approve")
async def approve_strategy(strategy_id: str, db: DB, user: CurrentUser) -> dict:
    # risk_increasing: creates Approval row bound to user + strategy_version
    return {"detail": "stub"}
