from typing import Generator
from config.schema import LLMConfig
from llm.adapter import LLMAdapter
from llm.adapters.openai_compat import OpenAICompatAdapter
from llm.text_processor import TextProcessor, ProcessedText


class LLMManager:
    def __init__(self, config: LLMConfig, character_prompt: str = ""):
        self._config = config
        self._adapter: LLMAdapter = self._create_adapter(config)
        self._processor = TextProcessor()
        self._character_prompt = character_prompt
        self._history: list[dict] = []

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
        for chunk in self._adapter.stream_chat(messages):
            full_response += chunk
            result = self._processor.process(full_response)
            yield result

        self._history.append({"role": "assistant", "content": full_response})

    def get_history(self) -> list[dict]:
        return self._history.copy()

    def clear_history(self) -> None:
        self._history.clear()
