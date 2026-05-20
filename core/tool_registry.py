from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from core.mcp_host import MCPHost
from core.plugin_host import PluginHost


@dataclass(frozen=True)
class ToolEntry:
    name: str
    source: str
    qualified_name: str
    schema: dict[str, Any]

    def as_openai_tool(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.qualified_name,
                "description": self.schema.get("description", ""),
                "parameters": self.schema["parameters"],
            },
        }


class ToolRegistry:
    def __init__(self, plugin_host: PluginHost | None = None, mcp_host: MCPHost | None = None):
        self._plugin_host = plugin_host
        self._mcp_host = mcp_host
        self._entries: list[ToolEntry] = []
        self.refresh()

    def refresh(self) -> None:
        self._entries = []
        if self._plugin_host:
            for spec in self._plugin_host.tool_specs():
                function = spec["function"]
                self._entries.append(ToolEntry(
                    name=function["name"].split("__", 1)[-1],
                    source="plugin",
                    qualified_name=function["name"],
                    schema={
                        "description": function.get("description", ""),
                        "parameters": function["parameters"],
                    },
                ))
        if self._mcp_host:
            for spec in self._mcp_host.tool_specs():
                function = spec["function"]
                self._entries.append(ToolEntry(
                    name=function["name"].split("__", 1)[-1],
                    source="mcp",
                    qualified_name=function["name"],
                    schema={
                        "description": function.get("description", ""),
                        "parameters": function["parameters"],
                    },
                ))

    def tool_specs(self) -> list[dict[str, Any]]:
        return [entry.as_openai_tool() for entry in self._entries]

    def call_tool(self, qualified_name: str, arguments: dict[str, Any]) -> Any:
        if self._plugin_host:
            try:
                return self._plugin_host.call_tool(qualified_name, arguments)
            except ValueError:
                pass
        if self._mcp_host:
            return self._mcp_host.call_tool(qualified_name, arguments)
        raise ValueError(f"Unknown tool: {qualified_name}")
