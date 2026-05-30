import logging
from collections.abc import Iterator
from urllib.parse import urlsplit, urlunsplit

import requests

from config.schema import AgentConfig, TTSConfig, TTSRuntimeConfig
from core.log_types import LogChannel, LogLevel, build_log_event
from tts.adapter import TTSAdapter
from tts.types import TTSAudioFormat, TTSStreamEvent


_LOGGER = logging.getLogger(__name__)


class GPTSoVITSAdapter(TTSAdapter):
    _REFERENCE_CAPABILITY_CACHE: dict[str, str] = {}
    PCM_STREAM_CHUNK_SIZE = 32 * 1024
    WAV_RESPONSE_CHUNK_SIZE = 64 * 1024

    REFERENCE_MODE_AUTO = "auto"
    REFERENCE_MODE_INLINE = "inline"
    REFERENCE_MODE_SESSION_PRELOAD = "session_preload"
    REFERENCE_MODE_SERVER_MANAGED = "server_managed"

    AUDIO_MODE_AUTO = "auto"
    AUDIO_MODE_PCM_STREAM = "pcm_stream"
    AUDIO_MODE_WAV = "wav"

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

    def __init__(
        self,
        config: TTSConfig,
        session_id: str | None = None,
        runtime_config: TTSRuntimeConfig | None = None,
        log_service=None,
    ):
        self._api_url = self._normalize_api_url(config.api_url)
        self._prepare_url = self._build_prepare_url(self._api_url)
        self._ref_audio_path = config.ref_audio_path.strip()
        self._reference_mode = self._normalize_reference_mode(config.reference_mode)
        self._audio_mode = self._normalize_audio_mode(config.audio_mode)
        self._prompt_lang = self._normalize_prompt_lang(config.prompt_lang)
        self._output_lang = self._normalize_prompt_lang(config.output_lang)
        self._prompt_text = config.prompt_text.strip()
        self._session_id = (session_id or "").strip()
        self._session_extension_enabled: bool | None = True if self._session_id else False
        self._session_audio_mode_override: str | None = None
        self._runtime_config = runtime_config or AgentConfig().tts_runtime
        self._session = requests.Session()
        self._prepare_attempted = False
        self._reference_state = self._initial_reference_state()
        self._log_service = log_service

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

    @classmethod
    def _normalize_audio_mode(cls, audio_mode: str) -> str:
        normalized = (audio_mode or cls.AUDIO_MODE_AUTO).strip().lower()
        if normalized in {cls.AUDIO_MODE_AUTO, cls.AUDIO_MODE_PCM_STREAM, cls.AUDIO_MODE_WAV}:
            return normalized
        return cls.AUDIO_MODE_AUTO

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

    def _is_strict_original_mode(self) -> bool:
        return self._audio_mode == self.AUDIO_MODE_WAV and self._reference_mode == self.REFERENCE_MODE_INLINE

    def _reference_mode_allows_session_extension(self) -> bool:
        return self._reference_mode in {
            self.REFERENCE_MODE_AUTO,
            self.REFERENCE_MODE_SESSION_PRELOAD,
            self.REFERENCE_MODE_SERVER_MANAGED,
        }

    def _supports_session_extension(self) -> bool:
        return bool(
            self._session_id
            and self._session_extension_enabled is not False
            and not self._is_strict_original_mode()
            and self._reference_mode_allows_session_extension()
        )

    def needs_reference_prepare(self) -> bool:
        return bool(
            self._ref_audio_path
            and self._reference_mode in {self.REFERENCE_MODE_AUTO, self.REFERENCE_MODE_SESSION_PRELOAD}
            and not self._prepare_attempted
        )

    def _can_use_session_preload_extension(self) -> bool:
        return bool(self._supports_session_extension() and self._prompt_lang and self._prompt_text)

    def _build_reference_payload(self, include_session_id: bool = True) -> dict[str, str]:
        payload = {"refer_audio_path": self._ref_audio_path}
        if include_session_id and self._can_use_session_preload_extension():
            payload["session_id"] = self._session_id
            payload["prompt_lang"] = self._prompt_lang
            payload["prompt_text"] = self._prompt_text
        return payload

    def _mark_session_extension_disabled(self) -> None:
        self._session_extension_enabled = False

    def _mark_session_extension_enabled(self) -> None:
        if self._session_id:
            self._session_extension_enabled = True

    def prepare_reference(self) -> bool | None:
        if not self.needs_reference_prepare():
            return None
        self._prepare_attempted = True
        self._reference_state = "preparing"
        try:
            used_session_extension = self._can_use_session_preload_extension()
            if self._supports_session_extension() and not used_session_extension:
                self._mark_session_extension_disabled()
            resp = self._session.get(
                self._prepare_url,
                params=self._build_reference_payload(include_session_id=used_session_extension),
                timeout=30,
            )
            if used_session_extension and self._is_session_extension_error(resp):
                retry_resp = self._session.get(
                    self._prepare_url,
                    params=self._build_reference_payload(include_session_id=False),
                    timeout=30,
                )
                if 200 <= retry_resp.status_code < 300:
                    self._mark_session_extension_disabled()
                    self._reference_state = "prepared"
                    self._record_log_event(
                        level=LogLevel.INFO,
                        event_type="tts.reference_prepared",
                        summary="reference prepared with inline fallback",
                        details={"reference_mode": self._reference_mode},
                    )
                    if self._reference_mode == self.REFERENCE_MODE_AUTO:
                        self._REFERENCE_CAPABILITY_CACHE.setdefault(self._api_url, "prepared")
                    return True
                resp = retry_resp
            if 200 <= resp.status_code < 300:
                if used_session_extension:
                    self._mark_session_extension_enabled()
                self._reference_state = "prepared"
                self._record_log_event(
                    level=LogLevel.INFO,
                    event_type="tts.reference_prepared",
                    summary="reference prepared",
                    details={"reference_mode": self._reference_mode},
                )
                if self._reference_mode == self.REFERENCE_MODE_AUTO:
                    self._REFERENCE_CAPABILITY_CACHE.setdefault(self._api_url, "prepared")
                return True
            _LOGGER.warning("[TTS] GPT-SoVITS reference prepare failed with HTTP %s: %s", resp.status_code, resp.text[:200])
        except Exception as exc:
            _LOGGER.warning("[TTS] GPT-SoVITS reference prepare failed: %s", exc)
        self._reference_state = "fallback_inline"
        self._record_log_event(
            level=LogLevel.WARN,
            event_type="tts.reference_prepare_failed",
            summary="reference prepare failed",
            details={"reference_mode": self._reference_mode},
        )
        if self._reference_mode == self.REFERENCE_MODE_AUTO:
            self._REFERENCE_CAPABILITY_CACHE[self._api_url] = self.REFERENCE_MODE_INLINE
        return False

    def get_session_audio_mode(self) -> str:
        if self._session_audio_mode_override:
            return self._session_audio_mode_override
        if self._is_strict_original_mode():
            return self.AUDIO_MODE_WAV
        if self._audio_mode == self.AUDIO_MODE_AUTO:
            return self.AUDIO_MODE_PCM_STREAM
        return self._audio_mode

    def force_session_audio_mode(self, audio_mode: str) -> None:
        normalized = self._normalize_audio_mode(audio_mode)
        self._session_audio_mode_override = None if normalized == self.AUDIO_MODE_AUTO else normalized

    def _effective_audio_mode(self) -> str:
        return self.get_session_audio_mode()

    def _should_send_explicit_audio_fields(self, audio_mode: str) -> bool:
        if self._is_strict_original_mode():
            return False
        if self._session_audio_mode_override is not None:
            return True
        return audio_mode in {self.AUDIO_MODE_PCM_STREAM, self.AUDIO_MODE_WAV}

    def _build_audio_payload(self, audio_mode: str) -> dict[str, object]:
        if audio_mode == self.AUDIO_MODE_PCM_STREAM:
            return {
                "media_type": "raw",
                "streaming_mode": 3,
                "text_split_method": "cut5",
                "batch_size": 1,
                "parallel_infer": False,
                "split_bucket": False,
                "overlap_length": 2,
                "min_chunk_length": 12,
            }
        if audio_mode == self.AUDIO_MODE_WAV:
            return {
                "media_type": "wav",
                "streaming_mode": 0,
                "text_split_method": "cut5",
                "batch_size": 1,
                "parallel_infer": True,
                "split_bucket": True,
                "overlap_length": 2,
                "min_chunk_length": 16,
            }
        return {}

    def _build_tts_payload(
        self,
        text: str,
        include_reference: bool,
        audio_mode: str,
    ) -> dict[str, object]:
        payload: dict[str, object] = {"text": text, "text_lang": self._output_lang}
        if include_reference and self._ref_audio_path:
            payload["ref_audio_path"] = self._ref_audio_path
            if self._prompt_lang:
                payload["prompt_lang"] = self._prompt_lang
            if self._prompt_text:
                payload["prompt_text"] = self._prompt_text
        if self._supports_session_extension():
            payload["session_id"] = self._session_id
        if self._should_send_explicit_audio_fields(audio_mode):
            payload.update(self._build_audio_payload(audio_mode))
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

    @staticmethod
    def _is_session_extension_error(resp) -> bool:
        text = (getattr(resp, "text", "") or "").lower()
        if "session_id" not in text:
            return False
        keywords = (
            "unknown",
            "unexpected",
            "unsupported",
            "invalid",
            "query",
            "field",
            "param",
        )
        return any(keyword in text for keyword in keywords)

    def _request_audio(self, payload: dict[str, object], audio_mode: str):
        wants_stream = audio_mode == self.AUDIO_MODE_PCM_STREAM
        read_timeout = self._runtime_config.pcm_read_timeout_seconds
        timeout = (30, read_timeout) if wants_stream else 30
        if wants_stream or self._should_send_explicit_audio_fields(audio_mode):
            try:
                return self._session.post(
                    self._api_url,
                    json=payload,
                    timeout=timeout,
                    stream=wants_stream,
                )
            except TypeError:
                pass
        return self._session.post(
            self._api_url,
            json=payload,
            timeout=timeout,
        )

    def _yield_wav_response(self, resp) -> Iterator[TTSStreamEvent]:
        yield TTSStreamEvent(
            kind="start",
            format=TTSAudioFormat(transport="wav", sample_rate=0, channels=0, sample_width=0),
        )
        content = getattr(resp, "content", b"") or b""
        for offset in range(0, len(content), self.WAV_RESPONSE_CHUNK_SIZE):
            yield TTSStreamEvent(kind="chunk", data=content[offset : offset + self.WAV_RESPONSE_CHUNK_SIZE])
        yield TTSStreamEvent(kind="end")
        return True

    def _yield_pcm_response(self, resp) -> Iterator[TTSStreamEvent]:
        headers = getattr(resp, "headers", {}) or {}
        yield TTSStreamEvent(
            kind="start",
            format=TTSAudioFormat(
                transport="pcm_stream",
                sample_rate=int(headers.get("X-Audio-Sample-Rate", "32000")),
                channels=int(headers.get("X-Audio-Channels", "1")),
                sample_width=int(headers.get("X-Audio-Sample-Width", "2")),
            ),
        )
        emitted = False
        try:
            for chunk in resp.iter_content(chunk_size=self.PCM_STREAM_CHUNK_SIZE):
                if not chunk:
                    continue
                emitted = True
                yield TTSStreamEvent(kind="chunk", data=chunk)
        except Exception as exc:
            _LOGGER.warning("[TTS] GPT-SoVITS PCM stream failed: %s", exc)
            yield TTSStreamEvent(kind="error", message=str(exc))
            return None
        if emitted:
            yield TTSStreamEvent(kind="end")
            return True
        return False

    def stream_synthesize(self, text: str) -> Iterator[TTSStreamEvent]:
        if self.needs_reference_prepare():
            self.prepare_reference()
        include_reference = self._should_include_reference()
        audio_mode = self._effective_audio_mode()
        allow_auto_retry = self._audio_mode == self.AUDIO_MODE_AUTO and audio_mode == self.AUDIO_MODE_PCM_STREAM
        yield from self._stream_request(text, include_reference, audio_mode, allow_auto_retry)

    def _stream_request(
        self,
        text: str,
        include_reference: bool,
        audio_mode: str,
        allow_auto_retry: bool,
        allow_session_retry: bool = True,
    ) -> Iterator[TTSStreamEvent]:
        payload = self._build_tts_payload(text, include_reference, audio_mode)
        self._record_log_event(
            level=LogLevel.INFO,
            event_type="tts.request_started",
            summary="tts request started",
            details={
                "audio_mode": audio_mode,
                "include_reference": include_reference,
                "text_length": len(text),
            },
        )
        try:
            resp = self._request_audio(payload, audio_mode)
        except Exception as exc:
            if allow_auto_retry and audio_mode == self.AUDIO_MODE_PCM_STREAM:
                success = yield from self._stream_request(
                    text,
                    include_reference,
                    self.AUDIO_MODE_WAV,
                    allow_auto_retry=False,
                )
                if success:
                    self.force_session_audio_mode(self.AUDIO_MODE_WAV)
                return success
            _LOGGER.warning("[TTS] GPT-SoVITS request failed: %s", exc)
            self._record_log_event(
                level=LogLevel.ERROR,
                event_type="tts.request_failed",
                summary="tts request failed",
                details={"error": str(exc), "audio_mode": audio_mode},
            )
            yield TTSStreamEvent(kind="error", message=str(exc))
            return False

        if resp.status_code == 200:
            self._record_log_event(
                level=LogLevel.INFO,
                event_type="tts.request_succeeded",
                summary="tts request succeeded",
                details={"audio_mode": audio_mode, "status_code": resp.status_code},
            )
            if audio_mode == self.AUDIO_MODE_PCM_STREAM:
                success = yield from self._yield_pcm_response(resp)
                if success:
                    return True
                if success is None:
                    return False
                if allow_auto_retry:
                    success = yield from self._stream_request(
                        text,
                        include_reference,
                        self.AUDIO_MODE_WAV,
                        allow_auto_retry=False,
                    )
                    if success:
                        self.force_session_audio_mode(self.AUDIO_MODE_WAV)
                    return success
                _LOGGER.warning("[TTS] GPT-SoVITS returned an empty PCM stream")
                yield TTSStreamEvent(kind="error", message="empty pcm stream")
                return False
            return (yield from self._yield_wav_response(resp))

        if (
            not include_reference
            and self._reference_mode != self.REFERENCE_MODE_SERVER_MANAGED
            and self._is_missing_reference_error(resp)
        ):
            self._reference_state = "fallback_inline"
            if self._reference_mode == self.REFERENCE_MODE_AUTO:
                self._REFERENCE_CAPABILITY_CACHE[self._api_url] = self.REFERENCE_MODE_INLINE
            return (yield from self._stream_request(text, True, audio_mode, allow_auto_retry))

        if allow_session_retry and "session_id" in payload and self._is_session_extension_error(resp):
            self._mark_session_extension_disabled()
            return (
                yield from self._stream_request(
                    text,
                    include_reference,
                    audio_mode,
                    allow_auto_retry,
                    allow_session_retry=False,
                )
            )

        if allow_auto_retry and audio_mode == self.AUDIO_MODE_PCM_STREAM:
            success = yield from self._stream_request(
                text,
                include_reference,
                self.AUDIO_MODE_WAV,
                allow_auto_retry=False,
            )
            if success:
                self.force_session_audio_mode(self.AUDIO_MODE_WAV)
            return success

        error_text = (getattr(resp, "text", "") or "")[:200]
        _LOGGER.warning("[TTS] GPT-SoVITS returned HTTP %s: %s", resp.status_code, error_text)
        self._record_log_event(
            level=LogLevel.ERROR,
            event_type="tts.request_http_error",
            summary="tts request http error",
            details={"status_code": resp.status_code, "error_text": error_text},
        )
        yield TTSStreamEvent(kind="error", message=f"HTTP {resp.status_code}")
        return False

    def _record_log_event(self, level: LogLevel, event_type: str, summary: str, details: dict) -> None:
        if self._log_service is None:
            return
        self._log_service.record(
            build_log_event(
                channel=LogChannel.SYSTEM,
                level=level,
                source="tts.gptsovits",
                event_type=event_type,
                session_id=self._session_id or "default-session",
                summary=summary,
                details=details,
            )
        )
