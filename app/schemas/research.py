from __future__ import annotations

from pydantic import BaseModel


class ResearchRunCreate(BaseModel):
    goal: str
    mode: str = "scan"
    ticker: str | None = None


class ResearchRunResponse(BaseModel):
    id: str
    goal: str
    mode: str
    status: str
    trials_count: int

    model_config = {"from_attributes": True}
