from typing import Generator
from openai import OpenAI
from llm.adapter import LLMAdapter, LLMStreamChunk, ToolCall
from config.schema import LLMConfig


class OpenAICompatAdapter(LLMAdapter):
    def __init__(self, config: LLMConfig):
        self._config = config
        self._client = OpenAI(api_key=config.api_key, base_url=config.base_url)

    def stream_chat(self, messages: list[dict], tools: list[dict] | None = None) -> Generator[str | LLMStreamChunk, None, None]:
        kwargs = dict(
            model=self._config.model,
            messages=messages,
            stream=True,
            temperature=self._config.temperature,
            max_tokens=self._config.max_tokens,
        )
        if tools:
            kwargs["tools"] = tools

        response = self._client.chat.completions.create(**kwargs)
        tool_calls: dict[int, dict[str, str]] = {}
        for chunk in response:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            reasoning = getattr(delta, "reasoning_content", None)
            if isinstance(reasoning, str) and reasoning:
                yield LLMStreamChunk(thinking=reasoning)
            if delta.content:
                yield delta.content
            for call_delta in delta.tool_calls or []:
                index = call_delta.index
                current = tool_calls.setdefault(index, {"id": "", "name": "", "arguments": ""})
                if call_delta.id:
                    current["id"] += call_delta.id
                if call_delta.function:
                    if call_delta.function.name:
                        current["name"] += call_delta.function.name
                    if call_delta.function.arguments:
                        current["arguments"] += call_delta.function.arguments

        if tool_calls:
            yield LLMStreamChunk(tool_calls=[
                ToolCall(
                    id=data["id"],
                    name=data["name"],
                    arguments=data["arguments"],
                )
                for _, data in sorted(tool_calls.items())
            ])
