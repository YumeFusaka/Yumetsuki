from abc import ABC, abstractmethod
from typing import Generator


class LLMAdapter(ABC):
    @abstractmethod
    def stream_chat(self, messages: list[dict], tools: list[dict] | None = None) -> Generator[str, None, None]:
        ...
