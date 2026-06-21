from __future__ import annotations

from typing import Any

from app.core.tools.base import Permission, Tool, ToolContext, ToolRegistry, ToolResult


class MockReadTool(Tool):
    name = "test_read"
    description = "A test read tool"
    permission = Permission.READ

    async def invoke(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        return ToolResult(success=True, data={"test": True})


class MockRiskIncreasingTool(Tool):
    name = "test_risk_increasing"
    description = "A test risk-increasing tool"
    permission = Permission.RISK_INCREASING

    async def invoke(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        return ToolResult(success=True)


def test_register_and_get():
    reg = ToolRegistry()
    tool = MockReadTool()
    reg.register(tool)
    assert reg.get("test_read") is tool


def test_list_by_permission():
    reg = ToolRegistry()
    reg.register(MockReadTool())
    reg.register(MockRiskIncreasingTool())
    read_tools = reg.list_tools(Permission.READ)
    assert len(read_tools) == 1
    assert read_tools[0].name == "test_read"


def test_agent_cannot_access_risk_increasing():
    reg = ToolRegistry()
    reg.register(MockReadTool())
    reg.register(MockRiskIncreasingTool())
    agent_tools = reg.available_for_agent()
    names = [t.name for t in agent_tools]
    assert "test_read" in names
    assert "test_risk_increasing" not in names


def test_deregister():
    reg = ToolRegistry()
    reg.register(MockReadTool())
    reg.deregister("test_read")
    assert reg.get("test_read") is None
