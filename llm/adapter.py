from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Generator


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: str


@dataclass
class LLMStreamChunk:
    content: str = ""
    tool_calls: list[ToolCall] | None = None


class LLMAdapter(ABC):
    @abstractmethod
    def stream_chat(self, messages: list[dict], tools: list[dict] | None = None) -> Generator[str | LLMStreamChunk, None, None]:
        ...
