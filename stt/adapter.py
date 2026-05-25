from abc import ABC, abstractmethod

from stt.types import STTResult


class STTAdapter(ABC):
    @abstractmethod
    def transcribe_wav(self, audio: bytes) -> STTResult:
        raise NotImplementedError
