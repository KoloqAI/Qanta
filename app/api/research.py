from __future__ import annotations

from fastapi import APIRouter

from app.deps import DB, CurrentUser

router = APIRouter()


@router.post("/runs")
async def start_research_run(db: DB, user: CurrentUser) -> dict:
    # M6 Tools+Agent: start a research run (goal or ticker) -> job_id
    return {"job_id": "stub"}


@router.get("/runs/{run_id}")
async def get_research_run(run_id: str, db: DB, user: CurrentUser) -> dict:
    # M6: status + proposed candidates
    return {"id": run_id, "status": "stub"}
