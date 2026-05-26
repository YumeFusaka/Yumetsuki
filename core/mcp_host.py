from __future__ import annotations

import json
import os
import shlex
import subprocess
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable, Protocol

import requests

from config.schema import MCPServerConfig

MCP_TOOL_SEPARATOR = "__"
MCP_PROTOCOL_VERSION = "2024-11-05"


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
    error_type: str = ""
    last_checked_at: float = 0.0
    tool_names: list[str] | None = None


class MCPSession(Protocol):
    def list_tools(self) -> list[MCPTool]:
        ...

    def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        ...

    def close(self) -> None:
        ...


class UnsupportedMCPSession:
    def __init__(self, server: MCPServerConfig):
        raise NotImplementedError(f"{server.transport} MCP transport is not implemented yet")


class MCPStdioSession:
    def __init__(self, server: MCPServerConfig):
        if not server.command.strip():
            raise ValueError("stdio MCP server command is empty")
        self._server = server
        self._next_id = 1
        self._lock = threading.Lock()
        self._process = subprocess.Popen(
            _split_command(server.command),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            bufsize=1,
        )
        self._request("initialize", {
            "protocolVersion": MCP_PROTOCOL_VERSION,
            "capabilities": {},
            "clientInfo": {
                "name": "Yumetsuki",
                "version": "0.1",
            },
        })
        self._notify("notifications/initialized", {})

    def list_tools(self) -> list[MCPTool]:
        result = self._request("tools/list", {})
        tools = []
        for item in result.get("tools", []):
            tools.append(MCPTool(
                name=item["name"],
                description=item.get("description", ""),
                input_schema=item.get("inputSchema") or item.get("input_schema") or {
                    "type": "object",
                    "properties": {},
                },
            ))
        return tools

    def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        result = self._request("tools/call", {
            "name": name,
            "arguments": arguments,
        })
        content = result.get("content")
        if isinstance(content, list):
            text_parts = [
                item.get("text", "")
                for item in content
                if isinstance(item, dict) and item.get("type") == "text"
            ]
            if text_parts:
                return "\n".join(text_parts)
        return result

    def close(self) -> None:
        if self._process.poll() is not None:
            return
        self._process.terminate()
        try:
            self._process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            self._process.kill()

    def _request(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            msg_id = self._next_id
            self._next_id += 1
            self._write({
                "jsonrpc": "2.0",
                "id": msg_id,
                "method": method,
                "params": params,
            })
            while True:
                message = self._read()
                if message.get("id") != msg_id:
                    continue
                if "error" in message:
                    raise RuntimeError(message["error"])
                return message.get("result", {})

    def _notify(self, method: str, params: dict[str, Any]) -> None:
        self._write({
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
        })

    def _write(self, message: dict[str, Any]) -> None:
        if not self._process.stdin:
            raise RuntimeError("MCP stdio stdin is closed")
        self._process.stdin.write(json.dumps(message, ensure_ascii=False) + "\n")
        self._process.stdin.flush()

    def _read(self) -> dict[str, Any]:
        if not self._process.stdout:
            raise RuntimeError("MCP stdio stdout is closed")
        line = self._process.stdout.readline()
        if not line:
            stderr = self._process.stderr.read() if self._process.stderr else ""
            raise RuntimeError(f"MCP stdio server closed stdout. {stderr}".strip())
        return json.loads(line)


class MCPHttpSession:
    def __init__(self, server: MCPServerConfig):
        if not server.url.strip():
            raise ValueError("MCP HTTP server url is empty")
        self._server = server
        self._session = requests.Session()
        self._next_id = 1
        self._endpoint = server.url.strip()
        self._headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        self._timeout = max(1, int(server.request_timeout_seconds or 10))
        self._request("initialize", {
            "protocolVersion": MCP_PROTOCOL_VERSION,
            "capabilities": {},
            "clientInfo": {
                "name": "Yumetsuki",
                "version": "0.1",
            },
        })
        self._notify("notifications/initialized", {})

    def list_tools(self) -> list[MCPTool]:
        result = self._request("tools/list", {})
        tools = []
        for item in result.get("tools", []):
            tools.append(MCPTool(
                name=item["name"],
                description=item.get("description", ""),
                input_schema=item.get("inputSchema") or item.get("input_schema") or {
                    "type": "object",
                    "properties": {},
                },
            ))
        return tools

    def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        result = self._request("tools/call", {
            "name": name,
            "arguments": arguments,
        })
        content = result.get("content")
        if isinstance(content, list):
            text_parts = [
                item.get("text", "")
                for item in content
                if isinstance(item, dict) and item.get("type") == "text"
            ]
            if text_parts:
                return "\n".join(text_parts)
        return result

    def close(self) -> None:
        self._session.close()

    def _request(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        msg_id = self._next_id
        self._next_id += 1
        response = self._session.post(
            self._endpoint,
            headers=self._headers,
            json={
                "jsonrpc": "2.0",
                "id": msg_id,
                "method": method,
                "params": params,
            },
            timeout=self._timeout,
        )
        response.raise_for_status()
        message = self._decode_response(response.text, response.headers.get("Content-Type", ""))
        if "error" in message:
            raise RuntimeError(message["error"])
        return message.get("result", {})

    def _notify(self, method: str, params: dict[str, Any]) -> None:
        self._session.post(
            self._endpoint,
            headers=self._headers,
            json={
                "jsonrpc": "2.0",
                "method": method,
                "params": params,
            },
            timeout=self._timeout,
        ).raise_for_status()

    def _decode_response(self, body: str, content_type: str) -> dict[str, Any]:
        if "text/event-stream" in content_type:
            for line in body.splitlines():
                line = line.strip()
                if line.startswith("data:"):
                    return json.loads(line[5:].strip())
            raise RuntimeError("Empty SSE response from MCP server")
        return json.loads(body or "{}")


class MCPHost:
    def __init__(
        self,
        servers: list[MCPServerConfig],
        session_factory: Callable[[MCPServerConfig], MCPSession] | None = None,
    ):
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
                    last_checked_at=time.time(),
                    tool_names=[],
                ))
                continue

            attempts = max(0, int(server.retry_attempts)) + 1
            last_error: Exception | None = None
            for _ in range(attempts):
                try:
                    session = self._create_session(server)
                    tools = session.list_tools()
                    self._sessions[server.name] = session
                    self._tools[server.name] = tools
                    self.statuses.append(MCPServerStatus(
                        server=server.name,
                        transport=server.transport,
                        connected=True,
                        tools_count=len(tools),
                        message="connected",
                        last_checked_at=time.time(),
                        tool_names=[tool.name for tool in tools],
                    ))
                    last_error = None
                    break
                except Exception as exc:
                    last_error = exc

            if last_error is not None:
                self.statuses.append(MCPServerStatus(
                    server=server.name,
                    transport=server.transport,
                    connected=False,
                    message=str(last_error),
                    error_type=last_error.__class__.__name__,
                    last_checked_at=time.time(),
                    tool_names=[],
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

    def _create_session(self, server: MCPServerConfig) -> MCPSession:
        if self._session_factory:
            return self._session_factory(server)
        if server.transport == "stdio":
            return MCPStdioSession(server)
        if server.transport == "sse":
            return MCPHttpSession(server)
        return UnsupportedMCPSession(server)


def _split_command(command: str) -> list[str]:
    parts = shlex.split(command, posix=os.name != "nt")
    if os.name == "nt":
        return [part.strip('"') for part in parts]
    return parts
