from pathlib import Path

import pytest

from core.plugin_host import PluginHost, PluginLoadError
from sdk.base import BasePlugin, tool


class DemoPlugin(BasePlugin):
    name = "demo"
    description = "Demo plugin"

    @tool(description="Echo input text")
    def echo(self, text: str) -> str:
        return text


def test_tool_decorator_registers_schema():
    plugin = DemoPlugin()
    tools = plugin.tools()

    assert len(tools) == 1
    assert tools[0].name == "echo"
    assert tools[0].description == "Echo input text"
    assert tools[0].parameters["properties"]["text"]["type"] == "string"
    assert tools[0].parameters["required"] == ["text"]
    assert plugin.call_tool("echo", {"text": "hello"}) == "hello"


def test_unknown_tool_raises_value_error():
    plugin = DemoPlugin()

    with pytest.raises(ValueError, match="Unknown tool"):
        plugin.call_tool("missing", {})


def test_plugin_host_loads_plugins_and_calls_tools(tmp_path):
    plugin_dir = tmp_path / "plugins" / "echo_plugin"
    plugin_dir.mkdir(parents=True)
    (plugin_dir / "plugin.py").write_text(
        """
from sdk.base import BasePlugin, tool

class Plugin(BasePlugin):
    name = "echo"
    description = "Echo utilities"

    @tool(description="Echo text")
    def echo(self, text: str) -> str:
        return text
""",
        encoding="utf-8",
    )

    host = PluginHost(tmp_path / "plugins")
    host.load()

    assert [plugin.name for plugin in host.plugins] == ["echo"]
    assert host.tool_specs()[0]["function"]["name"] == "echo__echo"
    assert host.call_tool("echo__echo", {"text": "hi"}) == "hi"


def test_plugin_host_reports_load_errors(tmp_path):
    plugin_dir = tmp_path / "plugins" / "broken"
    plugin_dir.mkdir(parents=True)
    (plugin_dir / "plugin.py").write_text("raise RuntimeError('boom')", encoding="utf-8")

    host = PluginHost(tmp_path / "plugins")
    host.load()

    assert len(host.errors) == 1
    assert isinstance(host.errors[0], PluginLoadError)
    assert host.errors[0].plugin == "broken"
