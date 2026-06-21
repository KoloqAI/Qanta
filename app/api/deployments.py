from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.deps import DB, CurrentUser
from app import state

router = APIRouter()


class CreateDeploymentBody(BaseModel):
    strategy_id: str
    mode: str = "paper"  # paper | live


class PromoteBody(BaseModel):
    reason: str = ""


@router.post("")
async def create_deployment(
    body: CreateDeploymentBody, db: DB, user: CurrentUser
) -> dict:
    """Create a new deployment. Live mode is risk_increasing and requires
    human confirmation -- returns an error directing the user to confirm."""
    strategy = await state.registry.get(body.strategy_id)
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")

    if body.mode == "live":
        # risk_increasing: do NOT auto-deploy live
        raise HTTPException(
            status_code=400,
            detail=(
                "Live deployment is risk_increasing. "
                "Deploy in paper mode first, then promote via "
                "POST /deployments/{id}/promote with human confirmation."
            ),
        )

    # Paper deployment is allowed
    deployment_id = str(uuid.uuid4())
    deployment = {
        "id": deployment_id,
        "strategy_id": body.strategy_id,
        "strategy_name": strategy.get("name", "Untitled"),
        "mode": "paper",
        "status": "active",
        "pnl": 0.0,
    }
    state.deployments[deployment_id] = deployment

    # Start in the execution runtime
    await state.runtime.start(deployment_id)

    await state.audit_log.log(
        actor="user",
        action="deployment_created",
        subject_type="deployment",
        subject_id=deployment_id,
        payload={"strategy_id": body.strategy_id, "mode": "paper"},
        user_id=user.get("id"),
    )

    return deployment


@router.get("")
async def list_deployments(db: DB, user: CurrentUser) -> list[dict]:
    """List all deployments."""
    result = []
    for dep_id, dep in state.deployments.items():
        runtime_active = dep_id in state.runtime._active
        result.append({**dep, "runtime_active": runtime_active})
    return result


@router.post("/{deployment_id}/pause")
async def pause_deployment(
    deployment_id: str, db: DB, user: CurrentUser
) -> dict:
    """Pause a deployment. This is risk_reducing -- allowed without confirmation."""
    if deployment_id not in state.deployments:
        raise HTTPException(status_code=404, detail="Deployment not found")

    await state.runtime.stop(deployment_id)
    state.deployments[deployment_id]["status"] = "paused"

    await state.audit_log.log(
        actor="user",
        action="deployment_paused",
        subject_type="deployment",
        subject_id=deployment_id,
        user_id=user.get("id"),
    )

    return {"detail": "paused", "deployment_id": deployment_id}


@router.post("/{deployment_id}/flatten")
async def flatten_deployment(
    deployment_id: str, db: DB, user: CurrentUser
) -> dict:
    """Flatten all positions for a deployment. Risk_reducing -- allowed."""
    if deployment_id not in state.deployments:
        raise HTTPException(status_code=404, detail="Deployment not found")

    await state.broker.flatten_all()
    state.deployments[deployment_id]["status"] = "flattened"

    await state.audit_log.log(
        actor="user",
        action="deployment_flattened",
        subject_type="deployment",
        subject_id=deployment_id,
        user_id=user.get("id"),
    )

    await state.notifier.send(
        event="deployment_flattened",
        severity="warning",
        payload={"deployment_id": deployment_id},
    )

    return {"detail": "flattened", "deployment_id": deployment_id}


@router.post("/{deployment_id}/retire")
async def retire_deployment(
    deployment_id: str, db: DB, user: CurrentUser
) -> dict:
    """Retire a deployment -- stop and remove. Risk_reducing -- allowed."""
    if deployment_id not in state.deployments:
        raise HTTPException(status_code=404, detail="Deployment not found")

    await state.runtime.stop(deployment_id)
    await state.broker.flatten_all()
    state.deployments[deployment_id]["status"] = "retired"

    await state.audit_log.log(
        actor="user",
        action="deployment_retired",
        subject_type="deployment",
        subject_id=deployment_id,
        user_id=user.get("id"),
    )

    return {"detail": "retired", "deployment_id": deployment_id}


@router.post("/{deployment_id}/promote")
async def promote_deployment(
    deployment_id: str, body: PromoteBody, db: DB, user: CurrentUser
) -> dict:
    """Promote paper deployment to live. This is risk_increasing -- blocked.
    Returns an error explaining that live trading requires explicit human
    confirmation through the approval flow."""
    if deployment_id not in state.deployments:
        raise HTTPException(status_code=404, detail="Deployment not found")

    dep = state.deployments[deployment_id]
    if dep.get("mode") != "paper":
        raise HTTPException(
            status_code=400, detail="Only paper deployments can be promoted"
        )

    # risk_increasing: refuse and instruct user
    raise HTTPException(
        status_code=400,
        detail=(
            "Promoting to live is risk_increasing. "
            "This action requires human confirmation. "
            "The strategy must first be approved via the approval flow."
        ),
    )
