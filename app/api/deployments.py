from __future__ import annotations

from fastapi import APIRouter

from app.deps import DB, CurrentUser

router = APIRouter()


@router.post("")
async def create_deployment(db: DB, user: CurrentUser) -> dict:
    # M5 Execution: live needs Approval (risk_increasing)
    return {"detail": "stub"}


@router.get("")
async def list_deployments(db: DB, user: CurrentUser) -> list:
    return []


@router.post("/{deployment_id}/pause")
async def pause_deployment(deployment_id: str, db: DB, user: CurrentUser) -> dict:
    # risk_reducing
    return {"detail": "paused"}


@router.post("/{deployment_id}/flatten")
async def flatten_deployment(deployment_id: str, db: DB, user: CurrentUser) -> dict:
    # risk_reducing
    return {"detail": "flattened"}


@router.post("/{deployment_id}/retire")
async def retire_deployment(deployment_id: str, db: DB, user: CurrentUser) -> dict:
    # risk_reducing
    return {"detail": "retired"}


@router.post("/{deployment_id}/promote")
async def promote_deployment(deployment_id: str, db: DB, user: CurrentUser) -> dict:
    # risk_increasing: paper -> live, needs gate
    return {"detail": "stub"}
