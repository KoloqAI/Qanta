from __future__ import annotations

from fastapi import APIRouter

from app.deps import DB, CurrentUser

router = APIRouter()


@router.get("/connections")
async def get_connections(user: CurrentUser) -> dict:
    return {"broker": {}, "data": {}}


@router.put("/connections")
async def update_connections(user: CurrentUser, db: DB) -> dict:
    return {"detail": "stub"}


@router.get("/models")
async def get_models(user: CurrentUser) -> dict:
    return {"tiers": {}}


@router.put("/models")
async def update_models(user: CurrentUser, db: DB) -> dict:
    return {"detail": "stub"}


@router.get("/risk")
async def get_risk(user: CurrentUser) -> dict:
    return {"guardrails": {}}


@router.put("/risk")
async def update_risk(user: CurrentUser, db: DB) -> dict:
    return {"detail": "stub"}


@router.get("/validation")
async def get_validation(user: CurrentUser) -> dict:
    return {"thresholds": {}}


@router.put("/validation")
async def update_validation(user: CurrentUser, db: DB) -> dict:
    return {"detail": "stub"}


@router.get("/tools")
async def get_tools(user: CurrentUser) -> dict:
    return {"tools": []}


@router.put("/tools")
async def update_tools(user: CurrentUser, db: DB) -> dict:
    return {"detail": "stub"}


@router.get("/workflows")
async def get_workflows(user: CurrentUser) -> dict:
    return {"workflows": []}


@router.put("/workflows")
async def update_workflows(user: CurrentUser, db: DB) -> dict:
    return {"detail": "stub"}


@router.get("/account")
async def get_account(user: CurrentUser) -> dict:
    return {"user": {}}


@router.put("/account")
async def update_account(user: CurrentUser, db: DB) -> dict:
    return {"detail": "stub"}


@router.get("/appearance")
async def get_appearance(user: CurrentUser) -> dict:
    return {"theme": "system"}


@router.put("/appearance")
async def update_appearance(user: CurrentUser, db: DB) -> dict:
    return {"detail": "stub"}
