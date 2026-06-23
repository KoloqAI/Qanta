from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.deps import DB, CurrentUser
from app import state

router = APIRouter()


class ApproveBody(BaseModel):
    approved: bool = True
    reason: str = ""


@router.get("")
async def list_strategies(
    db: DB,
    user: CurrentUser,
    status: str | None = Query(None, description="Filter by strategy status"),
) -> list[dict]:
    """List all strategies, optionally filtered by status."""
    filters = {}
    if status:
        filters["status"] = status
    strategies = await state.registry.list_all(filters)
    return strategies


@router.get("/{strategy_id}")
async def get_strategy(strategy_id: str, db: DB, user: CurrentUser) -> dict:
    """Get full strategy detail including versions and validation report."""
    strategy = await state.registry.get(strategy_id)
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")

    spec = strategy.get("spec", {})
    validation = state.validation_reports.get(strategy_id, {})

    # Find active deployment for this strategy (if any)
    active_deployment = None
    for dep in state.deployments.values():
        if dep.get("strategy_version_id") == strategy_id and dep.get("status") in (
            "active", "paused",
        ):
            active_deployment = {
                "id": dep["id"],
                "mode": dep.get("mode", "paper"),
                "status": dep.get("status", "active"),
                "capital_budget": dep.get("capital_budget"),
            }
            break

    return {
        "id": strategy["id"],
        "name": strategy.get("name", "Untitled"),
        "ticker": strategy.get("family", ""),
        "version": spec.get("version", 1),
        "state": strategy.get("status", "draft"),
        "thesis": spec.get("thesis", ""),
        "confidence": validation.get("confidence_curve", []),
        "sharpe": validation.get("sharpe", 0),
        "pbo": validation.get("pbo", 0),
        "dsr": validation.get("dsr", 0),
        "max_dd": validation.get("max_dd", 0),
        "n_trades": validation.get("n_trades", 0),
        "win_rate": validation.get("win_rate", 0),
        "net_edge": validation.get("net_edge", 0),
        "equity_curve": validation.get("equity_curve", []),
        "red_team": validation.get("red_team", []),
        "regime_description": spec.get("regime", {}),
        "spec": spec,
        "deployment": active_deployment,
    }


@router.post("/{strategy_id}/validate")
async def validate_strategy(strategy_id: str, db: DB, user: CurrentUser) -> dict:
    """Run the validation gauntlet on a strategy. Calls run_validation directly
    since Arq is not running in dev."""
    strategy = await state.registry.get(strategy_id)
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")

    spec = strategy.get("spec", {})
    version = spec.get("version", 1)

    # Run validation directly (no worker queue in dev)
    from app.workers.tasks import run_validation

    job_id = str(uuid.uuid4())
    result = await run_validation(
        ctx={},
        strategy_version_id=f"{strategy_id}:v{version}",
        spec=spec,
    )

    # Also run backtest to capture additional metrics
    from app.workers.tasks import run_backtest

    bt_result = await run_backtest(
        ctx={},
        strategy_version_id=f"{strategy_id}:v{version}",
        window={"start": "2019-01-01", "end": "2023-12-31"},
        spec=spec,
    )

    # Red team concerns
    concerns = await state.author.red_team(spec)

    # Store the combined validation report
    report = {
        "passed": result.get("passed", False),
        "dsr": result.get("dsr", 0),
        "pbo": result.get("pbo", 0),
        "peer_hit": result.get("peer_hit", 0),
        "gates_version": result.get("gates_version", 0),
        "sharpe": bt_result.get("sharpe", 0),
        "net_edge": bt_result.get("net_edge", 0),
        "n_trades": bt_result.get("n_trades", 0),
        "win_rate": bt_result.get("win_rate", 0),
        "max_dd": bt_result.get("max_dd", 0),
        "confidence_curve": result.get("confidence_curve", []),
        "equity_curve": [],
        "red_team": concerns,
    }
    state.validation_reports[strategy_id] = report

    # Update strategy state if validation passed
    if result.get("passed"):
        await state.registry.update_state(strategy_id, version, "validated")
        strategy["status"] = "validated"

    await state.audit_log.log(
        actor="system",
        action="validation_complete",
        subject_type="strategy",
        subject_id=strategy_id,
        payload={"passed": result.get("passed", False), "job_id": job_id},
        user_id=user.get("id"),
    )

    return {"job_id": job_id, "status": result.get("status", "completed"), **report}


@router.post("/{strategy_id}/approve")
async def approve_strategy(
    strategy_id: str, body: ApproveBody, db: DB, user: CurrentUser
) -> dict:
    """Approve or reject a strategy.  Body: {approved: bool, reason: str}.
    Rejection reuses this endpoint with approved=false (there is no /reject route).
    Approval is risk_increasing and requires a passing validation report."""
    strategy = await state.registry.get(strategy_id)
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")

    spec = strategy.get("spec", {})
    version = spec.get("version", 1)

    if body.approved:
        from app.modules.validation.service import GATES_VERSION

        report = state.validation_reports.get(strategy_id, {})
        if not report.get("passed"):
            raise HTTPException(
                status_code=400,
                detail="Strategy must pass validation before approval. Run /validate first.",
            )
        if report.get("gates_version", 0) < GATES_VERSION:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Validation report is stale (gates_version "
                    f"{report.get('gates_version', 0)} < {GATES_VERSION}). "
                    "Re-validate with the current gate set."
                ),
            )

        await state.registry.update_state(strategy_id, version, "approved")
        strategy["status"] = "approved"

        await state.audit_log.log(
            actor="user",
            action="strategy_approved",
            subject_type="strategy",
            subject_id=strategy_id,
            payload={"approved": True, "reason": body.reason, "version": version},
            user_id=user.get("id"),
        )

        await state.notifier.send(
            event="strategy_approved",
            severity="info",
            payload={"strategy_id": strategy_id, "name": strategy.get("name")},
        )

        return {
            "detail": "approved",
            "strategy_id": strategy_id,
            "version": version,
            "reason": body.reason,
        }

    # Rejection path
    await state.registry.update_state(strategy_id, version, "rejected")
    strategy["status"] = "rejected"

    await state.audit_log.log(
        actor="user",
        action="strategy_rejected",
        subject_type="strategy",
        subject_id=strategy_id,
        payload={"approved": False, "reason": body.reason, "version": version},
        user_id=user.get("id"),
    )

    await state.notifier.send(
        event="strategy_rejected",
        severity="info",
        payload={
            "strategy_id": strategy_id,
            "name": strategy.get("name"),
            "reason": body.reason,
        },
    )

    return {
        "detail": "rejected",
        "strategy_id": strategy_id,
        "version": version,
        "reason": body.reason,
    }
