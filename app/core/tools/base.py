from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Literal

class Permission(str, Enum):
    READ = "read"
    RISK_REDUCING = "risk_reducing"
    RISK_INCREASING = "risk_increasing"

@dataclass
class ToolContext:
    user_id: str
    session_id: str
    metadata: dict[str, Any] = field(default_factory=dict)

@dataclass
class ToolResult:
    success: bool
    data: Any = None
    error: str | None = None

class Tool(ABC):
    name: str
    description: str
    permission: Permission
    cost_tier: str = "local"

    @abstractmethod
    async def invoke(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        ...

class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def deregister(self, name: str) -> None:
        self._tools.pop(name, None)

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def list_tools(self, permission: Permission | None = None) -> list[Tool]:
        tools = list(self._tools.values())
        if permission is not None:
            tools = [t for t in tools if t.permission == permission]
        return tools

    def available_for_agent(self) -> list[Tool]:
        """Agent can only access read and risk_reducing tools."""
        return [t for t in self._tools.values() if t.permission != Permission.RISK_INCREASING]

registry = ToolRegistry()
