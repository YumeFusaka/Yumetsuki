import requests
from urllib.parse import urlsplit, urlunsplit
from tts.adapter import TTSAdapter
from config.schema import TTSConfig


class GPTSoVITSAdapter(TTSAdapter):
    _REFERENCE_CAPABILITY_CACHE: dict[str, str] = {}
    REFERENCE_MODE_AUTO = "auto"
    REFERENCE_MODE_INLINE = "inline"
    REFERENCE_MODE_SESSION_PRELOAD = "session_preload"
    REFERENCE_MODE_SERVER_MANAGED = "server_managed"
    PREPARE_STATES = {
        "disabled",
        "inline",
        "preparing",
        "prepared",
        "fallback_inline",
        "server_managed",
    }
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
        self._prepare_url = self._build_prepare_url(self._api_url)
        self._ref_audio_path = config.ref_audio_path.strip()
        self._reference_mode = self._normalize_reference_mode(config.reference_mode)
        self._prompt_lang = self._normalize_prompt_lang(config.prompt_lang)
        self._output_lang = self._normalize_prompt_lang(config.output_lang)
        self._prompt_text = config.prompt_text.strip()
        self._session = requests.Session()
        self._prepare_attempted = False
        self._reference_state = self._initial_reference_state()

    @staticmethod
    def _normalize_api_url(api_url: str) -> str:
        parts = urlsplit(api_url.strip())
        path = (parts.path or "").rstrip("/")
        if path == "":
            path = "/tts"
        return urlunsplit((parts.scheme, parts.netloc, path, parts.query, parts.fragment))

    @staticmethod
    def _build_prepare_url(api_url: str) -> str:
        parts = urlsplit(api_url)
        path = (parts.path or "").rstrip("/")
        if path.endswith("/tts"):
            path = path[:-4]
        prepare_path = f"{path}/set_refer_audio" if path else "/set_refer_audio"
        return urlunsplit((parts.scheme, parts.netloc, prepare_path, parts.query, parts.fragment))

    @classmethod
    def _normalize_prompt_lang(cls, prompt_lang: str) -> str:
        normalized = prompt_lang.strip().lower()
        return cls.LANGUAGE_ALIASES.get(normalized, normalized)

    @classmethod
    def _normalize_reference_mode(cls, reference_mode: str) -> str:
        normalized = (reference_mode or cls.REFERENCE_MODE_AUTO).strip().lower()
        if normalized in {
            cls.REFERENCE_MODE_AUTO,
            cls.REFERENCE_MODE_INLINE,
            cls.REFERENCE_MODE_SESSION_PRELOAD,
            cls.REFERENCE_MODE_SERVER_MANAGED,
        }:
            return normalized
        return cls.REFERENCE_MODE_AUTO

    def _initial_reference_state(self) -> str:
        if not self._ref_audio_path:
            return "disabled"
        cached_mode = self._REFERENCE_CAPABILITY_CACHE.get(self._api_url)
        if self._reference_mode == self.REFERENCE_MODE_AUTO and cached_mode == self.REFERENCE_MODE_INLINE:
            return "fallback_inline"
        if self._reference_mode == self.REFERENCE_MODE_SERVER_MANAGED:
            return "server_managed"
        if self._reference_mode == self.REFERENCE_MODE_INLINE:
            return "inline"
        return "inline"

    def needs_reference_prepare(self) -> bool:
        return bool(
            self._ref_audio_path
            and self._reference_mode in {self.REFERENCE_MODE_AUTO, self.REFERENCE_MODE_SESSION_PRELOAD}
            and not self._prepare_attempted
        )

    def _build_reference_payload(self) -> dict[str, str]:
        return {"refer_audio_path": self._ref_audio_path}

    def prepare_reference(self) -> bool | None:
        if not self.needs_reference_prepare():
            return None
        self._prepare_attempted = True
        self._reference_state = "preparing"
        try:
            resp = self._session.get(
                self._prepare_url,
                params=self._build_reference_payload(),
                timeout=30,
            )
            if 200 <= resp.status_code < 300:
                self._reference_state = "prepared"
                if self._reference_mode == self.REFERENCE_MODE_AUTO:
                    self._REFERENCE_CAPABILITY_CACHE.setdefault(self._api_url, "prepared")
                return True
            print(f"[TTS] GPT-SoVITS reference prepare failed with HTTP {resp.status_code}: {resp.text[:200]}")
        except Exception as exc:
            print(f"[TTS] GPT-SoVITS reference prepare failed: {exc}")
        self._reference_state = "fallback_inline"
        if self._reference_mode == self.REFERENCE_MODE_AUTO:
            self._REFERENCE_CAPABILITY_CACHE[self._api_url] = self.REFERENCE_MODE_INLINE
        return False

    def _build_tts_payload(self, text: str, include_reference: bool) -> dict[str, str]:
        payload = {"text": text, "text_lang": self._output_lang}
        if include_reference and self._ref_audio_path:
            payload["ref_audio_path"] = self._ref_audio_path
            if self._prompt_lang:
                payload["prompt_lang"] = self._prompt_lang
            if self._prompt_text:
                payload["prompt_text"] = self._prompt_text
        return payload

    def _should_include_reference(self) -> bool:
        if not self._ref_audio_path:
            return False
        cached_mode = self._REFERENCE_CAPABILITY_CACHE.get(self._api_url)
        if self._reference_mode == self.REFERENCE_MODE_AUTO and cached_mode == self.REFERENCE_MODE_INLINE:
            return True
        if self._reference_mode == self.REFERENCE_MODE_SERVER_MANAGED:
            return False
        if self._reference_mode == self.REFERENCE_MODE_INLINE:
            return True
        return self._reference_state != "prepared"

    @staticmethod
    def _is_missing_reference_error(resp) -> bool:
        text = getattr(resp, "text", "") or ""
        normalized = text.lower()
        keywords = (
            "reference",
            "refer",
            "prompt",
            "missing",
            "not set",
            "ref_audio_path",
            "prompt_lang",
            "required",
        )
        return any(keyword in normalized for keyword in keywords)

    def synthesize(self, text: str) -> bytes | None:
        if self.needs_reference_prepare():
            self.prepare_reference()
        include_reference = self._should_include_reference()
        payload = self._build_tts_payload(text, include_reference)
        try:
            resp = self._session.post(
                self._api_url,
                json=payload,
                timeout=30,
            )
            if resp.status_code == 200:
                return resp.content
            if (
                not include_reference
                and self._reference_mode != self.REFERENCE_MODE_SERVER_MANAGED
                and self._is_missing_reference_error(resp)
            ):
                self._reference_state = "fallback_inline"
                if self._reference_mode == self.REFERENCE_MODE_AUTO:
                    self._REFERENCE_CAPABILITY_CACHE[self._api_url] = self.REFERENCE_MODE_INLINE
                retry_resp = self._session.post(
                    self._api_url,
                    json=self._build_tts_payload(text, True),
                    timeout=30,
                )
                if retry_resp.status_code == 200:
                    return retry_resp.content
                print(
                    f"[TTS] GPT-SoVITS inline fallback failed with HTTP "
                    f"{retry_resp.status_code}: {retry_resp.text[:200]}"
                )
            print(f"[TTS] GPT-SoVITS returned HTTP {resp.status_code}: {resp.text[:200]}")
            return None
        except Exception as exc:
            print(f"[TTS] GPT-SoVITS request failed: {exc}")
            return None
