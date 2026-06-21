from __future__ import annotations

from fastapi import APIRouter

from app.deps import DB, CurrentUser

router = APIRouter()


@router.post("/messages")
async def send_message(db: DB, user: CurrentUser) -> dict:
    return {
        "message": {
            "id": "msg-1",
            "role": "assistant",
            "content": "I can help you research strategies, analyze tickers, and manage your deployments. What would you like to explore?",
            "tool_calls": [],
            "staged_actions": [],
        }
    }


@router.post("/actions/{action_id}/confirm")
async def confirm_action(action_id: str, db: DB, user: CurrentUser) -> dict:
    # confirm a staged risk_increasing action
    return {"detail": "stub"}
