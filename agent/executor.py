from __future__ import annotations

from agent.planner import AgentPlan
from core.tool_registry import ToolRegistry


class AgentExecutor:
    def execute(self, plan: AgentPlan, tool_registry: ToolRegistry | None) -> str:
        if plan.mode != "tool" or not plan.tool_name:
            return ""
        if tool_registry is None:
            raise ValueError("Tool registry is required for tool execution")
        result = tool_registry.call_tool(plan.tool_name, dict(plan.arguments or {}))
        return str(result)
