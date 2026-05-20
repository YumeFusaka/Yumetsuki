from abc import ABC, abstractmethod


class TTSAdapter(ABC):
    @abstractmethod
    def synthesize(self, text: str) -> bytes | None:
        ...
