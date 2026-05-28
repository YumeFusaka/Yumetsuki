from typing import Generator

from core.log_types import LogChannel
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
    def __init__(self):
        self.calls = []

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

    def call_tool(self, name: str, arguments: dict, session_id: str = "default-session") -> str:
        self.calls.append({"name": name, "arguments": arguments, "session_id": session_id})
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
    registry = FakeMCPRegistry()
    manager = LLMManager(LLMConfig(api_key="test"), tool_registry=registry)
    manager._adapter = adapter

    results = list(manager.chat_stream("查 memo"))

    assert results[-1].clean_text == "查到了 memo"
    assert adapter.calls[0]["tools"][0]["function"]["name"] == "notes__search"
    assert adapter.calls[1]["messages"][-1]["content"] == "notes__search:memo"
    assert registry.calls[0]["session_id"] == "default-session"


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


class FailingAdapter(LLMAdapter):
    def stream_chat(self, messages: list[dict], tools: list[dict] | None = None):
        raise TimeoutError("Request timed out")


def test_llm_manager_records_failure_event_before_reraising():
    captured = []

    class _LogService:
        def record(self, event):
            captured.append(event)

    manager = LLMManager(LLMConfig(api_key="test"), log_service=_LogService(), session_id="s1")
    manager._adapter = FailingAdapter()

    try:
        list(manager.chat_stream("会超时吗"))
    except TimeoutError:
        pass
    else:
        raise AssertionError("Expected TimeoutError")

    failure = next(event for event in captured if event.event_type == "llm.stream_failed")
    assert failure.channel == LogChannel.SYSTEM
    assert failure.session_id == "s1"
    assert "Request timed out" in failure.details["error"]


class SearchToolAdapter(LLMAdapter):
    def __init__(self):
        self.calls: list[dict] = []

    def stream_chat(self, messages: list[dict], tools: list[dict] | None = None):
        self.calls.append({"messages": messages, "tools": tools})
        if len(self.calls) == 1:
            yield LLMStreamChunk(tool_calls=[
                ToolCall(
                    id="call_search",
                    name="system_control__search_in_browser",
                    arguments='{"query": "搜索天气预报"}',
                )
            ])
        else:
            yield "已搜索"


class SearchRegistry:
    def __init__(self):
        self.calls = []

    def tool_specs(self) -> list[dict]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "system_control__search_in_browser",
                    "description": "使用系统默认浏览器直接搜索关键词",
                    "parameters": {
                        "type": "object",
                        "properties": {"query": {"type": "string"}},
                        "required": ["query"],
                    },
                },
            }
        ]

    def call_tool(self, name: str, arguments: dict, session_id: str = "default-session") -> str:
        self.calls.append({"name": name, "arguments": arguments, "session_id": session_id})
        return f"searched:{arguments['query']}"


def test_llm_manager_normalizes_search_query_before_tool_dispatch():
    registry = SearchRegistry()
    adapter = SearchToolAdapter()
    manager = LLMManager(LLMConfig(api_key="test"), tool_registry=registry, session_id="s1")
    manager._adapter = adapter

    results = list(manager.chat_stream("搜索天气预报"))

    assert results[-1].clean_text == "已搜索"
    assert registry.calls == [{
        "name": "system_control__search_in_browser",
        "arguments": {"query": "天气预报"},
        "session_id": "s1",
    }]


class WebSessionOpenAdapter(LLMAdapter):
    def __init__(self):
        self.calls: list[dict] = []

    def stream_chat(self, messages: list[dict], tools: list[dict] | None = None):
        self.calls.append({"messages": messages, "tools": tools})
        if len(self.calls) == 1:
            yield LLMStreamChunk(tool_calls=[
                ToolCall(id="call_browser", name="web_automation__web_session_open", arguments="{}")
            ])
        else:
            yield "无法直接接管系统默认浏览器"


class WebSessionRegistry:
    def __init__(self):
        self.calls = []

    def tool_specs(self) -> list[dict]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "web_automation__web_session_open",
                    "description": "打开一个由 Playwright 控制的持续浏览器会话",
                    "parameters": {"type": "object", "properties": {}, "required": []},
                },
            }
        ]

    def call_tool(self, name: str, arguments: dict, session_id: str = "default-session") -> str:
        self.calls.append({"name": name, "arguments": arguments, "session_id": session_id})
        return "opened"


def test_llm_manager_blocks_implicit_web_session_open_for_default_browser_context():
    events = []
    registry = WebSessionRegistry()
    adapter = WebSessionOpenAdapter()
    manager = LLMManager(
        LLMConfig(api_key="test"),
        tool_registry=registry,
        log_service=type("_LogService", (), {"record": lambda _self, event: events.append(event)})(),
        session_id="s1",
    )
    manager._adapter = adapter

    results = list(manager.chat_stream("点击浏览器里的第二个条目"))

    assert results[-1].clean_text == "无法直接接管系统默认浏览器"
    assert registry.calls == []
    blocked = next(event for event in events if event.event_type == "llm.tool_call_blocked")
    assert blocked.level.value == "warn"
    assert blocked.details["reason"] == "web_session_open_requires_explicit_automation_request"


def test_llm_manager_allows_explicit_web_automation_session_open():
    registry = WebSessionRegistry()
    adapter = WebSessionOpenAdapter()
    manager = LLMManager(LLMConfig(api_key="test"), tool_registry=registry, session_id="s1")
    manager._adapter = adapter

    list(manager.chat_stream("打开 Playwright 自动化浏览器"))

    assert registry.calls == [{"name": "web_automation__web_session_open", "arguments": {}, "session_id": "s1"}]
