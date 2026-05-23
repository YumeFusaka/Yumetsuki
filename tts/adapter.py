from abc import ABC, abstractmethod
from collections.abc import Iterable

from tts.types import TTSStreamEvent


class TTSAdapter(ABC):
    @abstractmethod
    def stream_synthesize(self, text: str) -> Iterable[TTSStreamEvent]:
        raise NotImplementedError

    def synthesize(self, text: str) -> bytes | None:
        chunks: list[bytes] = []
        for event in self.stream_synthesize(text):
            if event.kind == "error":
                return None
            if event.kind == "chunk" and event.data is not None:
                chunks.append(event.data)
        if not chunks:
            return None
        return b"".join(chunks)
