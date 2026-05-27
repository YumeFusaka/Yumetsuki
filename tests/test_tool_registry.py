from config.schema import MCPServerConfig
from core.mcp_host import MCPHost, MCPTool
from core.plugin_host import PluginHost
from core.tool_registry import ToolRegistry
from sdk.base import BasePlugin, tool


class DemoPlugin(BasePlugin):
    name = "demo"
    description = "Demo plugin"

    @tool(description="Echo")
    def echo(self, text: str) -> str:
        return text


class FakeMCPSession:
    def __init__(self, server: MCPServerConfig):
        self.server = server

    def list_tools(self) -> list[MCPTool]:
        return [
            MCPTool(
                name="search",
                description="Search",
                input_schema={
                    "type": "object",
                    "properties": {"query": {"type": "string"}},
                    "required": ["query"],
                },
            )
        ]

    def call_tool(self, name: str, arguments: dict):
        return f"{self.server.name}:{name}:{arguments['query']}"

    def close(self) -> None:
        pass


def test_tool_registry_combines_plugin_and_mcp_tools(tmp_path):
    plugin_host = PluginHost(tmp_path / "plugins")
    plugin_host.plugins = [DemoPlugin()]
    mcp_host = MCPHost([MCPServerConfig(name="notes", transport="stdio", command="python server.py")], session_factory=FakeMCPSession)
    mcp_host.connect_all()

    registry = ToolRegistry(plugin_host=plugin_host, mcp_host=mcp_host)

    specs = registry.tool_specs()
    assert [spec["function"]["name"] for spec in specs] == ["demo__echo", "notes__search"]
    assert [entry.qualified_name for entry in registry.entries()] == ["demo__echo", "notes__search"]
    assert registry.entries()[0].source_name == "demo"
    assert registry.entries()[1].source_name == "notes"
    assert registry.entries()[1].parameter_summary() == "query*:string"
    assert registry.counts_by_source() == {"plugin": 1, "mcp": 1}
    assert registry.call_tool("demo__echo", {"text": "hi"}) == "hi"
    assert registry.call_tool("notes__search", {"query": "today"}) == "notes:search:today"


def test_tool_registry_refreshes_snapshot(tmp_path):
    plugin_host = PluginHost(tmp_path / "plugins")
    plugin_host.plugins = []
    mcp_host = MCPHost([], session_factory=FakeMCPSession)

    registry = ToolRegistry(plugin_host=plugin_host, mcp_host=mcp_host)
    assert registry.tool_specs() == []
    plugin_host.plugins = [DemoPlugin()]
    registry.refresh()
    assert registry.tool_specs()[0]["function"]["name"] == "demo__echo"
    assert registry.counts_by_source() == {"plugin": 1, "mcp": 0}


def test_tool_registry_records_plugin_and_mcp_specific_log_sources(tmp_path):
    class FakeLogService:
        def __init__(self):
            self.events = []

        def record(self, event):
            self.events.append(event)

    plugin_host = PluginHost(tmp_path / "plugins")
    plugin_host.plugins = [DemoPlugin()]
    mcp_host = MCPHost([MCPServerConfig(name="notes", transport="stdio", command="python server.py")], session_factory=FakeMCPSession)
    mcp_host.connect_all()
    log_service = FakeLogService()
    registry = ToolRegistry(plugin_host=plugin_host, mcp_host=mcp_host, log_service=log_service)

    registry.call_tool("demo__echo", {"text": "hi"})
    registry.call_tool("notes__search", {"query": "today"})

    assert [event.source for event in log_service.events] == ["plugin.demo", "mcp.notes"]
