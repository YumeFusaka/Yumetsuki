from typing import Generator
import json

from agent.tool_argument_normalizer import normalize_tool_arguments, should_block_web_session_open
from config.schema import LLMConfig
from core.log_types import LogChannel, LogLevel, build_log_event
from llm.adapter import LLMAdapter, LLMStreamChunk, ToolCall
from llm.adapters.openai_compat import OpenAICompatAdapter
from llm.text_processor import TextProcessor, ProcessedText
from core.tool_registry import ToolRegistry


class LLMManager:
    STREAM_PROGRESS_CHAR_INTERVAL = 80

    def __init__(
        self,
        config: LLMConfig,
        character_prompt: str = "",
        tool_registry: ToolRegistry | None = None,
        log_service=None,
        session_id: str = "default-session",
    ):
        self._config = config
        self._adapter: LLMAdapter = self._create_adapter(config)
        self._processor = TextProcessor()
        self._character_prompt = character_prompt
        self._history: list[dict] = []
        self._tool_registry = tool_registry
        self._log_service = log_service
        self._session_id = session_id

    def _create_adapter(self, config: LLMConfig) -> LLMAdapter:
        if config.provider == "openai_compat":
            return OpenAICompatAdapter(config)
        raise ValueError(f"Unknown provider: {config.provider}")

    def set_character(self, prompt: str) -> None:
        self._character_prompt = prompt
        self._history.clear()

    def _build_messages(
        self,
        user_input: str,
        session_context: str = "",
        extra_context: str = "",
    ) -> list[dict]:
        messages = []
        if self._character_prompt:
            messages.append({"role": "system", "content": self._character_prompt})
        if session_context:
            messages.append({"role": "system", "content": session_context})
        if extra_context:
            messages.append({
                "role": "system",
                "content": f"补充上下文：\n{extra_context}",
            })
        messages.extend(self._history)
        messages.append({"role": "user", "content": user_input})
        return messages

    def chat_stream(
        self,
        user_input: str,
        session_context: str = "",
        extra_context: str = "",
        allow_tools: bool = True,
    ) -> Generator[ProcessedText, None, None]:
        self._record_log_event(
            channel=LogChannel.SYSTEM,
            level=LogLevel.INFO,
            source="llm.manager",
            event_type="llm.stream_started",
            session_id=self._session_id,
            summary="LLM stream started",
            details={"allow_tools": allow_tools},
        )
        messages = self._build_messages(
            user_input,
            session_context=session_context,
            extra_context=extra_context,
        )
        self._history.append({"role": "user", "content": user_input})

        full_response = ""
        last_progress_log_length: int | None = None
        tools = self._tool_registry.tool_specs() if self._tool_registry and allow_tools else None
        try:
            for _ in range(3):
                tool_calls: list[ToolCall] = []
                for chunk in self._adapter.stream_chat(messages, tools=tools):
                    if isinstance(chunk, LLMStreamChunk):
                        if chunk.thinking:
                            yield ProcessedText(clean_text=full_response, emotion=None, thinking=chunk.thinking)
                        if chunk.content:
                            full_response += chunk.content
                            last_progress_log_length = self._record_stream_progress(
                                full_response,
                                last_progress_log_length,
                            )
                            yield self._processor.process(full_response)
                        if chunk.tool_calls:
                            tool_calls.extend(chunk.tool_calls)
                        continue
                    full_response += chunk
                    last_progress_log_length = self._record_stream_progress(
                        full_response,
                        last_progress_log_length,
                    )
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
                    messages.append(self._execute_tool_call(call, user_input=user_input))
            else:
                full_response += "\n\n工具调用次数过多，已停止继续执行。"
                last_progress_log_length = self._record_stream_progress(
                    full_response,
                    last_progress_log_length,
                )
                yield self._processor.process(full_response)
        except Exception as exc:
            self._record_log_event(
                channel=LogChannel.SYSTEM,
                level=LogLevel.ERROR,
                source="llm.manager",
                event_type="llm.stream_failed",
                session_id=self._session_id,
                summary="LLM stream failed",
                details={"error": str(exc)},
            )
            raise

        last_progress_log_length = self._record_stream_progress(
            full_response,
            last_progress_log_length,
            force=True,
        )
        self._history.append({"role": "assistant", "content": full_response})
        self._record_log_event(
            channel=LogChannel.SYSTEM,
            level=LogLevel.INFO,
            source="llm.manager",
            event_type="llm.stream_completed",
            session_id=self._session_id,
            summary="LLM stream completed",
            details={"response_length": len(full_response)},
        )

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

    def _execute_tool_call(self, call: ToolCall, user_input: str = "") -> dict:
        try:
            arguments = json.loads(call.arguments or "{}")
            arguments, normalization = normalize_tool_arguments(call.name, arguments, user_input)
            self._record_log_event(
                channel=LogChannel.SYSTEM,
                level=LogLevel.INFO,
                source="llm.manager",
                event_type="llm.tool_call_requested",
                session_id=self._session_id,
                summary=f"{call.name} requested",
                details={
                    "arguments": arguments,
                    "argument_normalization": normalization,
                    "input_preview": user_input[:120],
                },
            )
            if should_block_web_session_open(call.name, user_input):
                content = (
                    "Tool blocked: web_session_open 会打开 Playwright 自动化浏览器，"
                    "不能接管用户已经打开的系统默认浏览器。需要用户明确要求自动化浏览器会话后才会执行。"
                )
                self._record_log_event(
                    channel=LogChannel.SYSTEM,
                    level=LogLevel.WARN,
                    source="llm.manager",
                    event_type="llm.tool_call_blocked",
                    session_id=self._session_id,
                    summary=f"{call.name} blocked",
                    details={
                        "tool_name": call.name,
                        "reason": "web_session_open_requires_explicit_automation_request",
                        "input_preview": user_input[:120],
                        "arguments": arguments,
                    },
                    stage="tool_guard",
                )
                return {
                    "role": "tool",
                    "tool_call_id": call.id,
                    "name": call.name,
                    "content": content,
                }
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
        if self._tool_registry:
            try:
                return self._tool_registry.call_tool(
                    name,
                    arguments,
                    session_id=self._session_id,
                )
            except TypeError:
                return self._tool_registry.call_tool(name, arguments)
        return ""

    def _record_stream_progress(
        self,
        full_response: str,
        last_logged_length: int | None = None,
        force: bool = False,
    ) -> int | None:
        response_length = len(full_response)
        if response_length <= 0:
            return last_logged_length
        if last_logged_length is not None:
            advanced_by = response_length - last_logged_length
            if advanced_by <= 0:
                return last_logged_length
            if not force and advanced_by < self.STREAM_PROGRESS_CHAR_INTERVAL:
                return last_logged_length
        self._record_log_event(
            channel=LogChannel.SYSTEM,
            level=LogLevel.DEBUG,
            source="llm.manager",
            event_type="llm.stream_progress",
            session_id=self._session_id,
            summary="LLM stream progress",
            details={
                "response_length": response_length,
                "tail_preview": full_response[-80:],
            },
        )
        return response_length

    def _record_log_event(self, **kwargs) -> None:
        if self._log_service is None:
            return
        self._log_service.record(build_log_event(**kwargs))
