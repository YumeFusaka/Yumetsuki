import json
import sys
from pathlib import Path

from config.schema import MCPServerConfig
from core.mcp_host import MCPHost, MCPStdioSession, MCPTool


class FakeSession:
    def __init__(self, server: MCPServerConfig):
        self.server = server
        self.closed = False

    def list_tools(self) -> list[MCPTool]:
        return [
            MCPTool(
                name="search",
                description="Search notes",
                input_schema={
                    "type": "object",
                    "properties": {"query": {"type": "string"}},
                    "required": ["query"],
                },
            )
        ]

    def call_tool(self, name: str, arguments: dict) -> str:
        return f"{self.server.name}:{name}:{arguments['query']}"

    def close(self) -> None:
        self.closed = True


def test_mcp_host_connects_enabled_servers_and_exposes_tools():
    servers = [
        MCPServerConfig(name="notes", transport="stdio", command="python server.py"),
        MCPServerConfig(name="disabled", transport="stdio", command="python disabled.py", enabled=False),
    ]
    host = MCPHost(servers, session_factory=FakeSession)

    host.connect_all()

    assert len(host.statuses) == 2
    assert host.statuses[0].connected is True
    assert host.statuses[1].connected is False
    assert host.statuses[1].message == "disabled"
    assert host.tool_specs()[0]["function"]["name"] == "notes__search"
    assert host.call_tool("notes__search", {"query": "today"}) == "notes:search:today"


def test_mcp_host_records_connection_errors():
    class BrokenSession:
        def __init__(self, server: MCPServerConfig):
            raise RuntimeError("boom")

    host = MCPHost(
        [MCPServerConfig(name="broken", transport="stdio", command="python broken.py")],
        session_factory=BrokenSession,
    )

    host.connect_all()

    assert host.statuses[0].server == "broken"
    assert host.statuses[0].connected is False
    assert "boom" in host.statuses[0].message
    assert host.tool_specs() == []


def test_stdio_session_uses_jsonrpc_over_stdio(tmp_path):
    script = _write_fake_mcp_server(tmp_path)

    session = MCPStdioSession(MCPServerConfig(
        name="fake",
        transport="stdio",
        command=f'"{sys.executable}" -u "{script}"',
    ))
    try:
        tools = session.list_tools()
        assert tools[0].name == "search"
        assert session.call_tool("search", {"query": "hello"}) == "echo:hello"
    finally:
        session.close()


def test_mcp_host_uses_stdio_session_by_default(tmp_path):
    script = _write_fake_mcp_server(tmp_path)
    host = MCPHost([
        MCPServerConfig(
            name="fake",
            transport="stdio",
            command=f'"{sys.executable}" -u "{script}"',
        )
    ])

    host.connect_all()
    try:
        assert host.statuses[0].connected is True
        assert host.statuses[0].tools_count == 1
        assert host.call_tool("fake__search", {"query": "host"}) == "echo:host"
    finally:
        host.close()


def _write_fake_mcp_server(tmp_path: Path) -> Path:
    script = tmp_path / "server.py"
    script.write_text(
        """
import json
import sys

def read_message():
    line = sys.stdin.readline()
    if not line:
        return None
    return json.loads(line)

def write_message(message):
    sys.stdout.write(json.dumps(message) + "\\n")
    sys.stdout.flush()

while True:
    message = read_message()
    if message is None:
        break
    method = message.get("method")
    msg_id = message.get("id")
    if method == "initialize":
        write_message({
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "protocolVersion": message["params"]["protocolVersion"],
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "fake", "version": "0.1"},
            },
        })
    elif method == "tools/list":
        write_message({
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "tools": [
                    {
                        "name": "search",
                        "description": "Search notes",
                        "inputSchema": {
                            "type": "object",
                            "properties": {"query": {"type": "string"}},
                            "required": ["query"],
                        },
                    }
                ]
            },
        })
    elif method == "tools/call":
        args = message["params"]["arguments"]
        write_message({
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "content": [{"type": "text", "text": f"echo:{args['query']}"}]
            },
        })
    elif method == "notifications/initialized":
        pass
""",
        encoding="utf-8",
    )
    return script
