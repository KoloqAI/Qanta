from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class StrategyCreate(BaseModel):
    name: str
    domain: str = "short_term_equity"
    family: str | None = None
    rules: dict[str, Any]
    thesis: str


class StrategyResponse(BaseModel):
    id: str
    name: str
    domain: str
    family: str | None
    status: str

    model_config = {"from_attributes": True}


class StrategyVersionResponse(BaseModel):
    id: str
    version: int
    state: str
    thesis: str
    rules: dict[str, Any]

    model_config = {"from_attributes": True}


class StrategyDetailResponse(BaseModel):
    id: str
    name: str
    domain: str
    family: str | None
    status: str
    versions: list[StrategyVersionResponse]

    model_config = {"from_attributes": True}


class ApproveRequest(BaseModel):
    approved: bool
    reason: str | None = None
