import requests
from urllib.parse import urlsplit, urlunsplit
from tts.adapter import TTSAdapter
from config.schema import TTSConfig


class GPTSoVITSAdapter(TTSAdapter):
    LANGUAGE_ALIASES = {
        "jp": "ja",
        "ja-jp": "ja",
        "ja_jp": "ja",
        "zh-cn": "zh",
        "zh_cn": "zh",
        "cn": "zh",
        "en-us": "en",
        "en_us": "en",
    }

    def __init__(self, config: TTSConfig):
        self._api_url = self._normalize_api_url(config.api_url)
        self._ref_audio_path = config.ref_audio_path.strip()
        self._prompt_lang = self._normalize_prompt_lang(config.prompt_lang)
        self._output_lang = self._normalize_prompt_lang(config.output_lang)
        self._prompt_text = config.prompt_text.strip()

    @staticmethod
    def _normalize_api_url(api_url: str) -> str:
        parts = urlsplit(api_url.strip())
        path = (parts.path or "").rstrip("/")
        if path == "":
            path = "/tts"
        return urlunsplit((parts.scheme, parts.netloc, path, parts.query, parts.fragment))

    @classmethod
    def _normalize_prompt_lang(cls, prompt_lang: str) -> str:
        normalized = prompt_lang.strip().lower()
        return cls.LANGUAGE_ALIASES.get(normalized, normalized)

    def synthesize(self, text: str) -> bytes | None:
        try:
            payload = {"text": text, "text_lang": self._output_lang}
            if self._ref_audio_path:
                payload["ref_audio_path"] = self._ref_audio_path
            if self._ref_audio_path and self._prompt_lang:
                payload["prompt_lang"] = self._prompt_lang
            if self._ref_audio_path and self._prompt_text:
                payload["prompt_text"] = self._prompt_text
            resp = requests.post(
                self._api_url,
                json=payload,
                timeout=30,
            )
            if resp.status_code == 200:
                return resp.content
            print(f"[TTS] GPT-SoVITS returned HTTP {resp.status_code}: {resp.text[:200]}")
            return None
        except Exception as exc:
            print(f"[TTS] GPT-SoVITS request failed: {exc}")
            return None
