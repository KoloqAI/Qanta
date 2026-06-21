from __future__ import annotations

from pathlib import Path

import yaml
from fastapi import APIRouter
from pydantic import BaseModel

from app.deps import DB, CurrentUser
from app.config import settings
from app import state

router = APIRouter()


def _load_yaml(filename: str) -> dict:
    """Load a YAML config file from the config directory."""
    path = Path(settings.config_dir) / filename
    if path.exists():
        with open(path) as f:
            return yaml.safe_load(f) or {}
    return {}


# ---------------------------------------------------------------------------
# Connections
# ---------------------------------------------------------------------------


@router.get("/connections")
async def get_connections(user: CurrentUser) -> dict:
    """Return broker connection status from config."""
    return {
        "broker": {
            "host": settings.ibkr_host,
            "port": settings.ibkr_port,
            "client_id": settings.ibkr_client_id,
            "connected": False,  # Paper broker -- no real connection
        },
        "data": {
            "provider": "sample",  # Using SampleDataProvider in dev
            "status": "ok",
        },
        "redis": {
            "url": settings.redis_url,
        },
        "database": {
            "url": settings.database_url.split("@")[-1] if "@" in settings.database_url else "configured",
        },
    }


@router.put("/connections")
async def update_connections(user: CurrentUser, db: DB) -> dict:
    """Accept connection config update (no persistent storage yet)."""
    return {"detail": "accepted"}


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


@router.get("/models")
async def get_models(user: CurrentUser) -> dict:
    """Return LLM tier configuration from config/models.yaml."""
    return _load_yaml("models.yaml")


@router.put("/models")
async def update_models(user: CurrentUser, db: DB) -> dict:
    return {"detail": "accepted"}


# ---------------------------------------------------------------------------
# Risk
# ---------------------------------------------------------------------------


@router.get("/risk")
async def get_risk(user: CurrentUser) -> dict:
    """Return guardrail values from config/guardrails.yaml."""
    guardrails = _load_yaml("guardrails.yaml")
    # Also include live runtime state
    guardrails["kill_switch_active"] = state.risk_gate.is_killed
    return {"guardrails": guardrails}


@router.put("/risk")
async def update_risk(user: CurrentUser, db: DB) -> dict:
    """Risk guardrails are non-overridable by design. Accept but warn."""
    return {
        "detail": "accepted",
        "warning": "Guardrails are non-overridable. Config file is the source of truth.",
    }


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


@router.get("/validation")
async def get_validation(user: CurrentUser) -> dict:
    """Return validation thresholds from config/validation.yaml."""
    return _load_yaml("validation.yaml")


@router.put("/validation")
async def update_validation(user: CurrentUser, db: DB) -> dict:
    return {"detail": "accepted"}


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


@router.get("/tools")
async def get_tools(user: CurrentUser) -> dict:
    """Return registered tools from the ToolRegistry."""
    tools = state.tool_registry.list_tools()
    return {
        "tools": [
            {
                "name": t.name,
                "description": t.description,
                "permission": t.permission.value,
                "cost_tier": t.cost_tier,
            }
            for t in tools
        ]
    }


@router.put("/tools")
async def update_tools(user: CurrentUser, db: DB) -> dict:
    return {"detail": "accepted"}


# ---------------------------------------------------------------------------
# Workflows
# ---------------------------------------------------------------------------


@router.get("/workflows")
async def get_workflows(user: CurrentUser) -> dict:
    return {"workflows": []}


@router.put("/workflows")
async def update_workflows(user: CurrentUser, db: DB) -> dict:
    return {"detail": "accepted"}


# ---------------------------------------------------------------------------
# Account
# ---------------------------------------------------------------------------


@router.get("/account")
async def get_account(user: CurrentUser) -> dict:
    """Return current user info from the CurrentUser dependency."""
    return {
        "user": {
            "id": user.get("id", ""),
            "username": user.get("username", ""),
            "created_at": user.get("created_at", ""),
        }
    }


@router.put("/account")
async def update_account(user: CurrentUser, db: DB) -> dict:
    return {"detail": "accepted"}


# ---------------------------------------------------------------------------
# Appearance
# ---------------------------------------------------------------------------


class AppearanceBody(BaseModel):
    theme: str = "system"


@router.get("/appearance")
async def get_appearance(user: CurrentUser) -> dict:
    """Return saved appearance preference for the current user."""
    user_id = user.get("id", "")
    prefs = state.appearance_prefs.get(user_id, {})
    return {"theme": prefs.get("theme", "system")}


@router.put("/appearance")
async def update_appearance(
    body: AppearanceBody, user: CurrentUser, db: DB
) -> dict:
    """Save appearance preference in memory."""
    user_id = user.get("id", "")
    state.appearance_prefs[user_id] = {"theme": body.theme}
    return {"detail": "saved", "theme": body.theme}
