from config.schema import ASRConfig
from stt.adapters.faster_whisper import FasterWhisperAdapter
from stt.types import STTResult


class STTManager:
    def __init__(self, config: ASRConfig, log_service=None, session_id: str = ""):
        self._adapter = self._create_adapter(config, log_service=log_service, session_id=session_id)

    @staticmethod
    def _create_adapter(config: ASRConfig, log_service=None, session_id: str = ""):
        engine = (config.engine or "none").strip().lower()
        if engine == "none":
            return None
        if engine == "faster_whisper":
            return FasterWhisperAdapter(config, log_service=log_service, session_id=session_id)
        return engine

    def transcribe_wav(self, audio: bytes) -> STTResult:
        if self._adapter is None:
            return STTResult(text="")
        if isinstance(self._adapter, str):
            return STTResult(text="", error=f"不支持的 STT 引擎：{self._adapter}")
        return self._adapter.transcribe_wav(audio)
