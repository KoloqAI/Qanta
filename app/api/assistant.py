from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.deps import DB, CurrentUser
from app.core.tools.base import Permission, ToolContext, ToolResult
from app import state

router = APIRouter()


class MessageBody(BaseModel):
    content: str


# ---------------------------------------------------------------------------
# Intent detection (simple keyword matching for now)
# ---------------------------------------------------------------------------

_READ_KEYWORDS = {
    "scan": ("universe_scan", {}),
    "universe": ("universe_scan", {}),
    "analyze": ("technical_analysis", {}),
    "analysis": ("technical_analysis", {}),
    "technical": ("technical_analysis", {}),
    "backtest": ("backtest", {}),
    "validate": ("validate", {}),
    "validation": ("validate", {}),
    "query": ("query_book", {}),
    "portfolio": ("query_book", {}),
    "positions": ("query_book", {}),
    "book": ("query_book", {}),
    "characterize": ("characterize_ticker", {}),
    "profile": ("characterize_ticker", {}),
    "author": ("author_strategy", {}),
    "compose": ("author_strategy", {}),
}

_RISK_REDUCING_KEYWORDS = {
    "pause": "pause_deployment",
    "flatten": "flatten_deployment",
    "stop": "pause_deployment",
    "halt": "pause_deployment",
}

_RISK_INCREASING_KEYWORDS = {
    "deploy": "deploy_strategy",
    "approve": "approve_strategy",
    "promote": "deploy_strategy",
    "live": "deploy_strategy",
}


def _extract_ticker(text: str) -> str | None:
    """Try to extract an uppercase ticker symbol from the message."""
    tokens = text.split()
    for token in tokens:
        clean = token.strip(".,!?()[]{}\"'")
        if clean.isupper() and 1 <= len(clean) <= 5 and clean.isalpha():
            # Skip common English words that look like tickers
            if clean in {"I", "A", "THE", "AND", "OR", "FOR", "TO", "IN", "ON", "AT", "IS"}:
                continue
            return clean
    return None


def _extract_deployment_id(text: str) -> str | None:
    """Try to extract a UUID-like deployment ID from the message."""
    tokens = text.split()
    for token in tokens:
        clean = token.strip(".,!?()[]{}\"'")
        if len(clean) == 36 and clean.count("-") == 4:
            return clean
    return None


def _detect_intent(text: str) -> tuple[str | None, str, dict]:
    """Return (tool_name, permission_category, extra_args) from message text."""
    lower = text.lower()

    # Check risk_increasing first (most restrictive)
    for keyword, tool_name in _RISK_INCREASING_KEYWORDS.items():
        if keyword in lower:
            args: dict = {}
            ticker = _extract_ticker(text)
            if ticker:
                args["ticker"] = ticker
            dep_id = _extract_deployment_id(text)
            if dep_id:
                args["deployment_id"] = dep_id
            return tool_name, "risk_increasing", args

    # Check risk_reducing
    for keyword, tool_name in _RISK_REDUCING_KEYWORDS.items():
        if keyword in lower:
            args = {}
            dep_id = _extract_deployment_id(text)
            if dep_id:
                args["deployment_id"] = dep_id
            return tool_name, "risk_reducing", args

    # Check READ tools
    for keyword, (tool_name, default_args) in _READ_KEYWORDS.items():
        if keyword in lower:
            args = dict(default_args)
            ticker = _extract_ticker(text)
            if ticker:
                args["ticker"] = ticker
            return tool_name, "read", args

    return None, "unknown", {}


@router.post("/messages")
async def send_message(body: MessageBody, db: DB, user: CurrentUser) -> dict:
    """Process a user message through the tool catalog.

    - READ tools: invoke and return result
    - RISK_REDUCING tools: invoke and return result
    - RISK_INCREASING tools: stage for human confirmation, do NOT execute
    """
    msg_id = str(uuid.uuid4())
    tool_name, category, args = _detect_intent(body.content)
    ctx = ToolContext(
        user_id=user.get("id", ""),
        session_id=msg_id,
    )

    # No matching tool -- return a helpful response
    if tool_name is None:
        return {
            "message": {
                "id": msg_id,
                "role": "assistant",
                "content": (
                    "I can help you research strategies, analyze tickers, "
                    "and manage your deployments. Try asking me to:\n"
                    "- scan the universe\n"
                    "- analyze AAPL\n"
                    "- backtest a strategy\n"
                    "- query the portfolio\n"
                    "- pause or flatten a deployment\n"
                ),
                "tool_calls": [],
                "staged_actions": [],
            }
        }

    tool = state.tool_registry.get(tool_name)
    if tool is None:
        return {
            "message": {
                "id": msg_id,
                "role": "assistant",
                "content": f"Tool '{tool_name}' is not registered.",
                "tool_calls": [],
                "staged_actions": [],
            }
        }

    # RISK_INCREASING: stage for human confirmation, do NOT execute
    if tool.permission == Permission.RISK_INCREASING:
        action_id = str(uuid.uuid4())
        staged = {
            "id": action_id,
            "tool_name": tool_name,
            "args": args,
            "user_id": user.get("id", ""),
            "status": "pending",
            "description": f"{tool.description} ({tool_name})",
        }
        state.staged_actions[action_id] = staged

        await state.audit_log.log(
            actor="assistant",
            action="action_staged",
            subject_type="tool",
            subject_id=tool_name,
            payload={"action_id": action_id, "args": args},
            user_id=user.get("id"),
        )

        return {
            "message": {
                "id": msg_id,
                "role": "assistant",
                "content": (
                    f"This action ({tool.description}) is risk-increasing "
                    f"and requires your confirmation. Review the staged action "
                    f"and confirm via POST /assistant/actions/{action_id}/confirm"
                ),
                "tool_calls": [],
                "staged_actions": [staged],
            }
        }

    # READ or RISK_REDUCING: invoke directly
    result: ToolResult = await tool.invoke(args, ctx)

    await state.audit_log.log(
        actor="assistant",
        action="tool_invoked",
        subject_type="tool",
        subject_id=tool_name,
        payload={"args": args, "success": result.success},
        user_id=user.get("id"),
    )

    return {
        "message": {
            "id": msg_id,
            "role": "assistant",
            "content": (
                f"Executed {tool_name} successfully."
                if result.success
                else f"Error running {tool_name}: {result.error or 'unknown error'}"
            ),
            "tool_calls": [
                {
                    "tool": tool_name,
                    "args": args,
                    "result": result.data,
                    "success": result.success,
                }
            ],
            "staged_actions": [],
        }
    }


@router.post("/actions/{action_id}/confirm")
async def confirm_action(action_id: str, db: DB, user: CurrentUser) -> dict:
    """Confirm and execute a previously staged risk_increasing action."""
    staged = state.staged_actions.get(action_id)
    if not staged:
        raise HTTPException(status_code=404, detail="Staged action not found")

    if staged["status"] != "pending":
        raise HTTPException(
            status_code=400,
            detail=f"Action already {staged['status']}",
        )

    tool_name = staged["tool_name"]
    tool = state.tool_registry.get(tool_name)
    if not tool:
        raise HTTPException(status_code=404, detail=f"Tool '{tool_name}' not found")

    ctx = ToolContext(
        user_id=user.get("id", ""),
        session_id=action_id,
    )

    result: ToolResult = await tool.invoke(staged["args"], ctx)
    staged["status"] = "confirmed" if result.success else "failed"

    await state.audit_log.log(
        actor="user",
        action="action_confirmed",
        subject_type="tool",
        subject_id=tool_name,
        payload={
            "action_id": action_id,
            "args": staged["args"],
            "success": result.success,
        },
        user_id=user.get("id"),
    )

    return {
        "action_id": action_id,
        "status": staged["status"],
        "tool": tool_name,
        "result": result.data,
        "success": result.success,
    }
