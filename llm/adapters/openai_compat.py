from typing import Generator
from openai import OpenAI
from llm.adapter import LLMAdapter
from config.schema import LLMConfig


class OpenAICompatAdapter(LLMAdapter):
    def __init__(self, config: LLMConfig):
        self._config = config
        self._client = OpenAI(api_key=config.api_key, base_url=config.base_url)

    def stream_chat(self, messages: list[dict], tools: list[dict] | None = None) -> Generator[str, None, None]:
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
        for chunk in response:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
