from io import BytesIO

from openai import OpenAI

from config.schema import ASRConfig
from stt.adapter import STTAdapter
from stt.types import STTResult


class OpenAIWhisperAdapter(STTAdapter):
    def __init__(self, config: ASRConfig):
        self._api_key = config.api_key
        self._base_url = config.base_url
        self._model = config.model or "whisper-1"
        self._language = config.language or "zh"
        self._client = None

    def transcribe_wav(self, audio: bytes) -> STTResult:
        if not audio:
            return STTResult(text="", language=self._language, error="录音内容为空")

        wav_file = BytesIO(audio)
        wav_file.name = "speech.wav"
        try:
            response = self._get_client().audio.transcriptions.create(
                model=self._model,
                file=("speech.wav", wav_file, "audio/wav"),
                language=self._language,
            )
        except Exception as exc:
            return STTResult(text="", language=self._language, error=str(exc))

        return STTResult(text=(getattr(response, "text", "") or "").strip(), language=self._language)

    def _get_client(self):
        if self._client is None:
            kwargs = {}
            if self._api_key:
                kwargs["api_key"] = self._api_key
            if self._base_url:
                kwargs["base_url"] = self._base_url
            self._client = OpenAI(**kwargs)
        return self._client
