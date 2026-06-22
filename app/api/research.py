from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.deps import DB, CurrentUser
from app import state

router = APIRouter()

_runs: dict[str, dict] = {}


class ResearchRunBody(BaseModel):
    goal: str = ""
    ticker: str | None = None


@router.post("/runs")
async def start_research_run(body: ResearchRunBody, db: DB, user: CurrentUser) -> dict:
    """Start a research run. Scans the universe, composes specs, red-teams them."""
    run_id = str(uuid.uuid4())
    goal = body.goal or f"Research opportunity in {body.ticker or 'the market'}"

    candidates = await state.domain.scan(goal, {})
    if body.ticker:
        candidates = [c for c in candidates if c["ticker"] == body.ticker] or candidates[:1]

    specs = []
    for c in candidates[:3]:
        spec = await state.author.author(
            f"{goal} opportunity in {c['ticker']}", {"ticker": c["ticker"]}
        )
        concerns = await state.author.red_team(spec)

        # Register each candidate strategy so it appears in Review Queue
        strategy = await state.registry.create(spec, user_id=user.get("id", ""))
        strategy["status"] = "pending_review"
        strategy["red_team"] = concerns

        specs.append({
            "strategy_id": strategy["id"],
            "spec": spec,
            "concerns": concerns,
            "ticker": c["ticker"],
        })

    run = {
        "id": run_id,
        "status": "completed",
        "goal": goal,
        "candidates": specs,
    }
    _runs[run_id] = run

    await state.audit_log.log(
        actor="system",
        action="research_run_completed",
        subject_type="research_run",
        subject_id=run_id,
        payload={"goal": goal, "n_candidates": len(specs)},
        user_id=user.get("id"),
    )

    return run


@router.get("/runs/{run_id}")
async def get_research_run(run_id: str, db: DB, user: CurrentUser) -> dict:
    """Get research run status and candidates."""
    run = _runs.get(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Research run not found")
    return run
