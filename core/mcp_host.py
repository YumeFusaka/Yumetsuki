from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from config.schema import MCPServerConfig

MCP_TOOL_SEPARATOR = "__"


@dataclass(frozen=True)
class MCPTool:
    name: str
    description: str
    input_schema: dict[str, Any]

    def as_openai_tool(self, qualified_name: str) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": qualified_name,
                "description": self.description,
                "parameters": self.input_schema,
            },
        }


@dataclass(frozen=True)
class MCPServerStatus:
    server: str
    transport: str
    connected: bool
    tools_count: int = 0
    message: str = ""


class MCPSession(Protocol):
    def list_tools(self) -> list[MCPTool]:
        ...

    def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        ...

    def close(self) -> None:
        ...


class UnimplementedMCPSession:
    def __init__(self, server: MCPServerConfig):
        raise NotImplementedError(f"{server.transport} MCP transport is not implemented yet")


class MCPHost:
    def __init__(self, servers: list[MCPServerConfig], session_factory=UnimplementedMCPSession):
        self._servers = servers
        self._session_factory = session_factory
        self._sessions: dict[str, MCPSession] = {}
        self._tools: dict[str, list[MCPTool]] = {}
        self.statuses: list[MCPServerStatus] = []

    def connect_all(self) -> None:
        self.close()
        self.statuses.clear()
        for server in self._servers:
            if not server.enabled:
                self.statuses.append(MCPServerStatus(
                    server=server.name,
                    transport=server.transport,
                    connected=False,
                    message="disabled",
                ))
                continue
            try:
                session = self._session_factory(server)
                tools = session.list_tools()
                self._sessions[server.name] = session
                self._tools[server.name] = tools
                self.statuses.append(MCPServerStatus(
                    server=server.name,
                    transport=server.transport,
                    connected=True,
                    tools_count=len(tools),
                    message="connected",
                ))
            except Exception as exc:
                self.statuses.append(MCPServerStatus(
                    server=server.name,
                    transport=server.transport,
                    connected=False,
                    message=str(exc),
                ))

    def tool_specs(self) -> list[dict[str, Any]]:
        specs: list[dict[str, Any]] = []
        for server_name, tools in self._tools.items():
            for tool in tools:
                specs.append(tool.as_openai_tool(f"{server_name}{MCP_TOOL_SEPARATOR}{tool.name}"))
        return specs

    def call_tool(self, qualified_name: str, arguments: dict[str, Any]) -> Any:
        server_name, sep, tool_name = qualified_name.partition(MCP_TOOL_SEPARATOR)
        if not sep:
            raise ValueError(f"Tool name must be qualified as server__tool: {qualified_name}")
        session = self._sessions.get(server_name)
        if not session:
            raise ValueError(f"Unknown MCP server: {server_name}")
        return session.call_tool(tool_name, arguments)

    def close(self) -> None:
        for session in self._sessions.values():
            session.close()
        self._sessions.clear()
        self._tools.clear()
