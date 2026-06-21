from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.deps import DB, CurrentUser
from app import state

router = APIRouter()


class DecideBody(BaseModel):
    approved: bool
    reason: str = ""


@router.get("/digest")
async def get_evolution_digest(db: DB, user: CurrentUser) -> dict:
    """Return the real evolution digest from the EvolutionLoopImpl."""
    return await state.evolution.get_digest()


@router.post("/proposals/{proposal_id}/decide")
async def decide_proposal(
    proposal_id: str, body: DecideBody, db: DB, user: CurrentUser
) -> dict:
    """Decide on a Tier-3 capability proposal. This is risk_increasing
    because it can add new capabilities, but it requires explicit human
    decision (approve/reject), which this endpoint captures."""
    result = await state.evolution.decide_tier3(
        proposal_id=proposal_id,
        approved=body.approved,
        reason=body.reason,
    )

    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])

    await state.audit_log.log(
        actor="user",
        action="proposal_decided",
        subject_type="proposal",
        subject_id=proposal_id,
        payload={
            "approved": body.approved,
            "reason": body.reason,
        },
        user_id=user.get("id"),
    )

    return result
