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

    completed_events = [
        event for event in log_service.events
        if event.event_type == "tool.call_completed"
    ]
    assert [event.source for event in completed_events] == ["plugin.demo", "mcp.notes"]


def test_tool_registry_records_started_and_completed_audit_events(tmp_path):
    class FakeLogService:
        def __init__(self):
            self.events = []

        def record(self, event):
            self.events.append(event)

    plugin_host = PluginHost(tmp_path / "plugins")
    plugin_host.plugins = [DemoPlugin()]
    log_service = FakeLogService()
    registry = ToolRegistry(plugin_host=plugin_host, log_service=log_service)

    assert registry.call_tool("demo__echo", {"text": "hello"}) == "hello"

    event_types = [event.event_type for event in log_service.events]
    assert event_types == ["tool.call_started", "tool.call_completed"]
    completed = log_service.events[-1]
    assert completed.details["qualified_name"] == "demo__echo"
    assert completed.details["tool_name"] == "echo"
    assert completed.details["source_type"] == "plugin"
    assert completed.details["source_name"] == "demo"
    assert completed.details["arguments_summary"]["text"] == "hello"
    assert completed.details["elapsed_ms"] >= 0
    assert completed.details["result_preview"] == "hello"


def test_tool_registry_audit_summarizes_long_arguments(tmp_path):
    class FakeLogService:
        def __init__(self):
            self.events = []

        def record(self, event):
            self.events.append(event)

    plugin_host = PluginHost(tmp_path / "plugins")
    plugin_host.plugins = [DemoPlugin()]
    registry = ToolRegistry(plugin_host=plugin_host, log_service=FakeLogService())
    long_text = "x" * 1200

    registry.call_tool("demo__echo", {"text": long_text})

    summary = registry._log_service.events[-1].details["arguments_summary"]["text"]
    assert len(summary) < len(long_text)
    assert summary.endswith("...<truncated>")


def test_tool_registry_audit_sanitizes_sensitive_arguments(tmp_path):
    class SensitiveArgsPlugin(BasePlugin):
        name = "sensitive"
        description = "Sensitive args plugin"

        @tool(description="Echo with sensitive args")
        def echo(self, text: str, api_key: str, url: str, model_path: str) -> str:
            return text

    class FakeLogService:
        def __init__(self):
            self.events = []

        def record(self, event):
            self.events.append(event)

    plugin_host = PluginHost(tmp_path / "plugins")
    plugin_host.plugins = [SensitiveArgsPlugin()]
    registry = ToolRegistry(plugin_host=plugin_host, log_service=FakeLogService())

    registry.call_tool(
        "sensitive__echo",
        {
            "text": "hello",
            "api_key": "sk-live-secret",
            "url": "http://user:pass@127.0.0.1:8000/v1?api_key=sk-live-secret",
            "model_path": "E:/private/models/faster-whisper-large-v3-turbo",
        },
    )

    summary = registry._log_service.events[-1].details["arguments_summary"]
    assert summary["api_key"] == "***"
    assert "user:pass" not in summary["url"]
    assert "sk-live-secret" not in summary["url"]
    assert summary["url"] == "http://***@127.0.0.1:8000/v1?api_key=***"
    assert summary["model_path"] == "***/faster-whisper-large-v3-turbo"


def test_tool_registry_records_failed_audit_event(tmp_path):
    class FailingPlugin(BasePlugin):
        name = "broken"
        description = "Broken plugin"

        @tool(description="Fail")
        def fail(self, text: str) -> str:
            raise RuntimeError("boom")

    class FakeLogService:
        def __init__(self):
            self.events = []

        def record(self, event):
            self.events.append(event)

    plugin_host = PluginHost(tmp_path / "plugins")
    plugin_host.plugins = [FailingPlugin()]
    log_service = FakeLogService()
    registry = ToolRegistry(plugin_host=plugin_host, log_service=log_service)

    try:
        registry.call_tool("broken__fail", {"text": "hello"})
    except RuntimeError:
        pass

    event_types = [event.event_type for event in log_service.events]
    assert event_types == ["tool.call_started", "tool.call_failed"]
    failed = log_service.events[-1]
    assert failed.details["error"] == "boom"
    assert failed.details["error_type"] == "RuntimeError"
