import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from config.schema import MCPServerConfig
from core.mcp_host import MCPHost, MCPHttpSession, MCPStdioSession, MCPTool


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


def test_mcp_host_status_includes_tool_names_and_checked_time():
    host = MCPHost(
        [MCPServerConfig(name="notes", transport="stdio", command="python server.py")],
        session_factory=FakeSession,
    )

    host.connect_all()

    status = host.statuses[0]
    assert status.connected is True
    assert status.tool_names == ["search"]
    assert status.error_type == ""
    assert status.last_checked_at > 0


def test_mcp_host_retries_connection_failures():
    attempts = {"count": 0}

    class FlakySession(FakeSession):
        def __init__(self, server: MCPServerConfig):
            attempts["count"] += 1
            if attempts["count"] == 1:
                raise RuntimeError("temporary")
            super().__init__(server)

    host = MCPHost(
        [MCPServerConfig(name="notes", transport="stdio", command="python server.py", retry_attempts=1)],
        session_factory=FlakySession,
    )

    host.connect_all()

    assert attempts["count"] == 2
    assert host.statuses[0].connected is True


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


def test_http_session_parses_json_response():
    server, thread, url = _start_http_mcp_server(response_mode="json")
    try:
        session = MCPHttpSession(MCPServerConfig(name="web", transport="sse", url=url))
        tools = session.list_tools()
        assert tools[0].name == "search"
        assert session.call_tool("search", {"query": "hello"}) == "json:hello"
        session.close()
    finally:
        server.shutdown()
        thread.join(timeout=2)


def test_http_session_parses_sse_response():
    server, thread, url = _start_http_mcp_server(response_mode="sse")
    try:
        session = MCPHttpSession(MCPServerConfig(name="web", transport="sse", url=url))
        tools = session.list_tools()
        assert tools[0].name == "search"
        assert session.call_tool("search", {"query": "hello"}) == "sse:hello"
        session.close()
    finally:
        server.shutdown()
        thread.join(timeout=2)


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


def _start_http_mcp_server(response_mode: str):
    class Handler(BaseHTTPRequestHandler):
        server_version = "TestMCP/0.1"

        def do_POST(self):
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length)
            message = json.loads(body.decode("utf-8"))
            method = message["method"]
            if method == "notifications/initialized":
                self._write_json({"ok": True})
                return
            msg_id = message["id"]

            if method == "initialize":
                result = {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "fake", "version": "0.1"},
                }
                self._write_json({"jsonrpc": "2.0", "id": msg_id, "result": result})
                return
            if method == "tools/list":
                result = {
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
                }
                self._write_json({"jsonrpc": "2.0", "id": msg_id, "result": result})
                return
            if method == "tools/call":
                args = message["params"]["arguments"]
                payload = {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {
                        "content": [{"type": "text", "text": f"{response_mode}:{args['query']}"}]
                    },
                }
                if response_mode == "sse":
                    self._write_sse(payload)
                else:
                    self._write_json(payload)
                return

            self.send_error(400)

        def _write_json(self, payload):
            data = json.dumps(payload).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _write_sse(self, payload):
            data = f"data: {json.dumps(payload)}\n\n".encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, format, *args):
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url = f"http://127.0.0.1:{server.server_address[1]}/mcp"
    return server, thread, url
