from config.schema import ASRConfig
from stt.adapters.faster_whisper import FasterWhisperAdapter
from stt.types import STTResult


class STTManager:
    def __init__(self, config: ASRConfig):
        self._adapter = self._create_adapter(config)

    @staticmethod
    def _create_adapter(config: ASRConfig):
        engine = (config.engine or "none").strip().lower()
        if engine == "none":
            return None
        if engine == "faster_whisper":
            return FasterWhisperAdapter(config)
        return engine

    def transcribe_wav(self, audio: bytes) -> STTResult:
        if self._adapter is None:
            return STTResult(text="")
        if isinstance(self._adapter, str):
            return STTResult(text="", error=f"不支持的 STT 引擎：{self._adapter}")
        return self._adapter.transcribe_wav(audio)
