from __future__ import annotations

from io import BytesIO

import requests

from config.schema import ASRConfig
from stt.adapter import STTAdapter
from stt.types import STTResult


class FasterWhisperAdapter(STTAdapter):
    def __init__(self, config: ASRConfig):
        self._api_url = (config.api_url or "http://127.0.0.1:8000").rstrip("/")
        self._model = config.model or "base"
        self._language = config.language or "zh"
        self._timeout = max(1, int(config.record_timeout_seconds) + 10)

    def transcribe_wav(self, audio: bytes) -> STTResult:
        if not audio:
            return STTResult(text="", language=self._language, error="录音内容为空")

        wav_file = BytesIO(audio)
        wav_file.name = "speech.wav"
        try:
            response = requests.post(
                f"{self._api_url}/transcribe",
                files={"file": ("speech.wav", wav_file, "audio/wav")},
                data={"model": self._model, "language": self._language},
                timeout=self._timeout,
            )
            response.raise_for_status()
            payload = response.json()
        except Exception as exc:
            return STTResult(text="", language=self._language, error=str(exc))

        text = (payload.get("text") or "").strip() if isinstance(payload, dict) else ""
        if not text:
            return STTResult(text="", language=self._language, error="本地 STT 服务返回格式无效")
        return STTResult(text=text, language=payload.get("language") or self._language)
