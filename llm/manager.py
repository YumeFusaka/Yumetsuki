from typing import Generator
import json

from core.mcp_host import MCPHost
from config.schema import LLMConfig
from core.plugin_host import PluginHost
from llm.adapter import LLMAdapter, LLMStreamChunk, ToolCall
from llm.adapters.openai_compat import OpenAICompatAdapter
from llm.text_processor import TextProcessor, ProcessedText


class LLMManager:
    def __init__(
        self,
        config: LLMConfig,
        character_prompt: str = "",
        plugin_host: PluginHost | None = None,
        mcp_host: MCPHost | None = None,
    ):
        self._config = config
        self._adapter: LLMAdapter = self._create_adapter(config)
        self._processor = TextProcessor()
        self._character_prompt = character_prompt
        self._history: list[dict] = []
        self._plugin_host = plugin_host
        self._mcp_host = mcp_host

    def _create_adapter(self, config: LLMConfig) -> LLMAdapter:
        if config.provider == "openai_compat":
            return OpenAICompatAdapter(config)
        raise ValueError(f"Unknown provider: {config.provider}")

    def set_character(self, prompt: str) -> None:
        self._character_prompt = prompt
        self._history.clear()

    def _build_messages(self, user_input: str) -> list[dict]:
        messages = []
        if self._character_prompt:
            messages.append({"role": "system", "content": self._character_prompt})
        messages.extend(self._history)
        messages.append({"role": "user", "content": user_input})
        return messages

    def chat_stream(self, user_input: str) -> Generator[ProcessedText, None, None]:
        messages = self._build_messages(user_input)
        self._history.append({"role": "user", "content": user_input})

        full_response = ""
        tools = []
        if self._plugin_host:
            tools.extend(self._plugin_host.tool_specs())
        if self._mcp_host:
            tools.extend(self._mcp_host.tool_specs())
        tools = tools or None
        for _ in range(3):
            tool_calls: list[ToolCall] = []
            for chunk in self._adapter.stream_chat(messages, tools=tools):
                if isinstance(chunk, LLMStreamChunk):
                    if chunk.content:
                        full_response += chunk.content
                        yield self._processor.process(full_response)
                    if chunk.tool_calls:
                        tool_calls.extend(chunk.tool_calls)
                    continue
                full_response += chunk
                yield self._processor.process(full_response)

            if not tool_calls:
                break

            assistant_message = {
                "role": "assistant",
                "content": full_response or None,
                "tool_calls": [self._tool_call_message(call) for call in tool_calls],
            }
            messages.append(assistant_message)
            for call in tool_calls:
                messages.append(self._execute_tool_call(call))
        else:
            full_response += "\n\n工具调用次数过多，已停止继续执行。"
            yield self._processor.process(full_response)

        self._history.append({"role": "assistant", "content": full_response})

    def get_history(self) -> list[dict]:
        return self._history.copy()

    def clear_history(self) -> None:
        self._history.clear()

    def _tool_call_message(self, call: ToolCall) -> dict:
        return {
            "id": call.id,
            "type": "function",
            "function": {
                "name": call.name,
                "arguments": call.arguments,
            },
        }

    def _execute_tool_call(self, call: ToolCall) -> dict:
        try:
            arguments = json.loads(call.arguments or "{}")
            result = self._dispatch_tool(call.name, arguments)
            content = str(result)
        except Exception as exc:
            content = f"Tool error: {exc}"
        return {
            "role": "tool",
            "tool_call_id": call.id,
            "name": call.name,
            "content": content,
        }

    def _dispatch_tool(self, name: str, arguments: dict) -> object:
        if self._plugin_host:
            try:
                return self._plugin_host.call_tool(name, arguments)
            except ValueError:
                pass
        if self._mcp_host:
            return self._mcp_host.call_tool(name, arguments)
        return ""
