from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class AssistantMessage(BaseModel):
    content: str


class ToolCallChip(BaseModel):
    tool: str
    status: str
    result_summary: str | None = None


class StagedAction(BaseModel):
    id: str
    action: str
    parameters: dict[str, Any]
    guardrails_applied: dict[str, Any] | None = None


class AssistantResponse(BaseModel):
    response: str
    grounded_data: list[dict[str, Any]] | None = None
    tool_calls: list[ToolCallChip] | None = None
    staged_actions: list[StagedAction] | None = None
