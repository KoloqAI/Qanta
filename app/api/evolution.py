from __future__ import annotations

from fastapi import APIRouter

from app.deps import DB, CurrentUser

router = APIRouter()


@router.get("/digest")
async def get_evolution_digest(db: DB, user: CurrentUser) -> dict:
    return {
        "promotions": [],
        "retirements": [],
        "discoveries": [],
        "proposals": [],
        "meta_lockbox": {"status": "not_evaluated"},
    }


@router.post("/proposals/{proposal_id}/decide")
async def decide_proposal(proposal_id: str, db: DB, user: CurrentUser) -> dict:
    # risk_increasing: approve/reject Tier-3
    return {"detail": "stub"}
