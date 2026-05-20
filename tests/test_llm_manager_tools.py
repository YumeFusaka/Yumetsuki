from typing import Generator

from core.plugin_host import PluginHost
from llm.adapter import LLMAdapter, LLMStreamChunk, ToolCall
from llm.manager import LLMManager
from sdk.base import BasePlugin, tool
from config.schema import LLMConfig


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
    adapter = FakeAdapter()
    manager = LLMManager(LLMConfig(api_key="test"), plugin_host=host)
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
