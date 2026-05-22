from typing import Generator

from core.plugin_host import PluginHost
from llm.adapter import LLMAdapter, LLMStreamChunk, ToolCall
from llm.manager import LLMManager
from sdk.base import BasePlugin, tool
from config.schema import LLMConfig
from core.tool_registry import ToolRegistry


class MathPlugin(BasePlugin):
    name = "math"
    description = "Math tools"

    @tool(description="Add two numbers")
    def add(self, a: int, b: int) -> int:
        return a + b


class FakeAdapter(LLMAdapter):
    def __init__(self):
        self.calls: list[dict] = []

    def stream_chat(self, messages: list[dict], tools: list[dict] | None = None) -> Generator[str | LLMStreamChunk, None, None]:
        self.calls.append({"messages": messages, "tools": tools})
        if len(self.calls) == 1:
            yield LLMStreamChunk(tool_calls=[
                ToolCall(
                    id="call_1",
                    name="math__add",
                    arguments='{"a": 2, "b": 3}',
                )
            ])
        else:
            yield "[emotion:开心]结果是 5"


def test_llm_manager_executes_plugin_tool_calls():
    host = PluginHost("missing")
    host.plugins = [MathPlugin()]
    registry = ToolRegistry(plugin_host=host)
    adapter = FakeAdapter()
    manager = LLMManager(LLMConfig(api_key="test"), tool_registry=registry)
    manager._adapter = adapter

    results = list(manager.chat_stream("2+3 等于多少？"))

    assert results[-1].clean_text == "结果是 5"
    assert results[-1].emotion == "开心"
    assert adapter.calls[0]["tools"][0]["function"]["name"] == "math__add"
    second_messages = adapter.calls[1]["messages"]
    assert second_messages[-2]["tool_calls"][0]["function"]["name"] == "math__add"
    assert second_messages[-1] == {
        "role": "tool",
        "tool_call_id": "call_1",
        "name": "math__add",
        "content": "5",
    }
    assert manager.get_history()[-1]["content"] == "[emotion:开心]结果是 5"


class FakeMCPRegistry:
    def tool_specs(self) -> list[dict]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "notes__search",
                    "description": "Search notes",
                    "parameters": {
                        "type": "object",
                        "properties": {"query": {"type": "string"}},
                        "required": ["query"],
                    },
                },
            }
        ]

    def call_tool(self, name: str, arguments: dict) -> str:
        return f"{name}:{arguments['query']}"


class FakeMCPAdapter(LLMAdapter):
    def __init__(self):
        self.calls: list[dict] = []

    def stream_chat(self, messages: list[dict], tools: list[dict] | None = None):
        self.calls.append({"messages": messages, "tools": tools})
        if len(self.calls) == 1:
            yield LLMStreamChunk(tool_calls=[
                ToolCall(id="call_mcp", name="notes__search", arguments='{"query": "memo"}')
            ])
        else:
            yield "查到了 memo"


def test_llm_manager_executes_mcp_tool_calls():
    adapter = FakeMCPAdapter()
    manager = LLMManager(LLMConfig(api_key="test"), tool_registry=FakeMCPRegistry())
    manager._adapter = adapter

    results = list(manager.chat_stream("查 memo"))

    assert results[-1].clean_text == "查到了 memo"
    assert adapter.calls[0]["tools"][0]["function"]["name"] == "notes__search"
    assert adapter.calls[1]["messages"][-1]["content"] == "notes__search:memo"


class NoToolAdapter(LLMAdapter):
    def __init__(self):
        self.calls: list[dict] = []

    def stream_chat(self, messages: list[dict], tools: list[dict] | None = None):
        self.calls.append({"messages": messages, "tools": tools})
        yield "普通回复"


def test_llm_manager_can_disable_tools_for_reply_only_phase():
    adapter = NoToolAdapter()
    manager = LLMManager(LLMConfig(api_key="test"), tool_registry=FakeMCPRegistry())
    manager._adapter = adapter

    results = list(manager.chat_stream("打开浏览器", allow_tools=False))

    assert results[-1].clean_text == "普通回复"
    assert adapter.calls[0]["tools"] is None
