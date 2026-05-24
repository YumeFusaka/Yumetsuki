from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Any

from core.log_types import LogChannel, LogLevel, build_log_event
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

    def parameter_summary(self) -> str:
        parameters = self.schema.get("parameters", {})
        properties = parameters.get("properties", {})
        required = set(parameters.get("required", []))
        if not properties:
            return "无参数"
        parts = []
        for name, info in properties.items():
            marker = "*" if name in required else ""
            parts.append(f"{name}{marker}:{info.get('type', 'any')}")
        return ", ".join(parts)


class ToolRegistry:
    def __init__(
        self,
        plugin_host: PluginHost | None = None,
        mcp_host: MCPHost | None = None,
        log_service=None,
    ):
        self._plugin_host = plugin_host
        self._mcp_host = mcp_host
        self._log_service = log_service
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

    def entries(self) -> list[ToolEntry]:
        return self._entries.copy()

    def counts_by_source(self) -> dict[str, int]:
        counts = {"plugin": 0, "mcp": 0}
        for entry in self._entries:
            counts[entry.source] = counts.get(entry.source, 0) + 1
        return counts

    def _record_log_event(self, **kwargs) -> None:
        if self._log_service is None:
            return
        self._log_service.record(build_log_event(**kwargs))

    def call_tool(
        self,
        qualified_name: str,
        arguments: dict[str, Any],
        session_id: str = "default-session",
        utterance_id: int | None = None,
    ) -> Any:
        started = time.perf_counter()
        if self._plugin_host:
            try:
                result = self._plugin_host.call_tool(qualified_name, arguments)
                self._record_log_event(
                    channel=LogChannel.SYSTEM,
                    level=LogLevel.INFO,
                    source="tool.registry",
                    event_type="tool.call_completed",
                    session_id=session_id,
                    utterance_id=utterance_id,
                    summary=f"{qualified_name} completed",
                    details={
                        "arguments": arguments,
                        "elapsed_ms": int((time.perf_counter() - started) * 1000),
                        "result_preview": str(result)[:200],
                    },
                )
                return result
            except ValueError:
                pass
            except Exception as exc:
                self._record_log_event(
                    channel=LogChannel.SYSTEM,
                    level=LogLevel.ERROR,
                    source="tool.registry",
                    event_type="tool.call_failed",
                    session_id=session_id,
                    utterance_id=utterance_id,
                    summary=f"{qualified_name} failed",
                    details={
                        "arguments": arguments,
                        "elapsed_ms": int((time.perf_counter() - started) * 1000),
                        "error": str(exc),
                    },
                )
                raise
        if self._mcp_host:
            try:
                result = self._mcp_host.call_tool(qualified_name, arguments)
                self._record_log_event(
                    channel=LogChannel.SYSTEM,
                    level=LogLevel.INFO,
                    source="tool.registry",
                    event_type="tool.call_completed",
                    session_id=session_id,
                    utterance_id=utterance_id,
                    summary=f"{qualified_name} completed",
                    details={
                        "arguments": arguments,
                        "elapsed_ms": int((time.perf_counter() - started) * 1000),
                        "result_preview": str(result)[:200],
                    },
                )
                return result
            except Exception as exc:
                self._record_log_event(
                    channel=LogChannel.SYSTEM,
                    level=LogLevel.ERROR,
                    source="tool.registry",
                    event_type="tool.call_failed",
                    session_id=session_id,
                    utterance_id=utterance_id,
                    summary=f"{qualified_name} failed",
                    details={
                        "arguments": arguments,
                        "elapsed_ms": int((time.perf_counter() - started) * 1000),
                        "error": str(exc),
                    },
                )
                raise
        raise ValueError(f"Unknown tool: {qualified_name}")
