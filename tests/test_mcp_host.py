from config.schema import MCPServerConfig
from core.mcp_host import MCPHost, MCPTool


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
