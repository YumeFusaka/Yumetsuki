# TTS PCM 低延迟模式 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 Yumetsuki 的 GPT-SoVITS 句级 TTS 管线增加 `auto / pcm_stream / wav` 三种音频模式，实现真正的 PCM 边收边播低延迟链路，并在自动模式下支持会话级 WAV 回退。

**Architecture:** 保留现有设置页、句级切分、翻译与参考音频预热逻辑，在 `tts/` 下新增流式事件抽象，在 `ui/chat/` 下新增独立的 PCM 播放后端，并让 `ChatWindow` 从“整句 bytes 排队”升级为“按 segment 处理流式事件和播放状态”。服务端协议信息通过 `GPTSoVITSAdapter` 统一封装，`session_id` 由聊天窗生命周期管理。

**Tech Stack:** Python, PySide6 QtMultimedia (`QMediaPlayer`, `QAudioSink`, `QIODevice`), requests, pytest

**Compatibility Guardrail:** 原版 GPT-SoVITS 兼容优先。所有 `session_id`、PCM 流式和结构化错误等能力都必须是显式扩展；未携带扩展字段的请求必须继续保持原版 `wav` / 非流式 / 显式参考字段行为。

**Historical Note:** 本计划形成于服务端正式兼容规范独立收口之前。凡涉及 `session_id`、PCM 流式或自动回退的实现片段，都必须服从 [docs/service-tts-compatibility.md](../../service-tts-compatibility.md)：优先适配原版接口，桌宠端差异只能通过参数、设置项和已文档化显式扩展协商接入，不得把新逻辑主线默认化。

---

## File Structure

- Modify: `config/schema.py`
  - 为 `TTSConfig` 增加 `audio_mode`
- Modify: `ui/settings/pages/api_page.py`
  - 新增 TTS 音频模式下拉框与 apply/reset 逻辑
- Modify: `tests/test_config.py`
  - 覆盖 `audio_mode` 的保存与重载
- Modify: `tests/test_settings_window.py`
  - 覆盖设置页音频模式选项、apply/reset、配置透传
- Create: `tts/types.py`
  - 定义 `TTSAudioFormat`、`TTSStreamEvent`
- Modify: `tts/adapter.py`
  - 把流式事件设为主接口，保留 `synthesize()` 兼容包装
- Modify: `tts/adapters/gptsovits.py`
  - 支持 `audio_mode`、`session_id`、低延迟参数映射、流式 PCM、自动 WAV 回退
- Modify: `tests/test_tts_adapter.py`
  - 覆盖新请求映射、`session_id`、自动回退、流式事件输出
- Create: `ui/chat/audio_backends.py`
  - 放置 `WavPlaybackBackend`、`PcmStreamPlaybackBackend` 与流式缓冲设备
- Create: `tests/test_audio_backends.py`
  - 对新后端做无真实设备测试
- Modify: `ui/chat/window.py`
  - 生成 `session_id`、消费 `TTSStreamEvent`、调度双播放后端、维护句段流式状态
- Modify: `tests/test_chat_tts_flow.py`
  - 覆盖流式事件顺序、PCM 首包即播、回退与清理
- Modify: `CLAUDE.md`
- Modify: `docs/README.md`
- Modify: `docs/architecture.md`
- Modify: `docs/development.md`

## Task 1: Persist `audio_mode` And Expose It In Settings

**Files:**
- Modify: `config/schema.py`
- Modify: `ui/settings/pages/api_page.py`
- Modify: `tests/test_config.py`
- Modify: `tests/test_settings_window.py`

- [ ] **Step 1: Write the failing config and settings tests**

```python
# tests/test_config.py
def test_save_and_reload_extended_tts_config(tmp_path):
    mgr = ConfigManager(config_dir=tmp_path)
    mgr.api.tts.engine = "gptsovits"
    mgr.api.tts.api_url = "http://127.0.0.1:9880"
    mgr.api.tts.audio_mode = "pcm_stream"
    mgr.api.tts.ref_audio_path = "data/audio/ref.wav"
    mgr.api.tts.reference_mode = "session_preload"
    mgr.api.tts.prompt_lang = "zh"
    mgr.api.tts.output_lang = "en"
    mgr.api.tts.prompt_text = "你好，我是参考音频"
    mgr.save_api()

    mgr2 = ConfigManager(config_dir=tmp_path)
    assert mgr2.api.tts.audio_mode == "pcm_stream"


# tests/test_settings_window.py
def test_api_page_tts_audio_mode_apply_and_reset():
    _app()
    config = APIConfig()
    page = APIPage(config)

    assert page._tts_audio_mode.currentData() == "auto"

    page._tts_audio_mode.setCurrentIndex(1)
    page.apply()
    assert config.tts.audio_mode == "pcm_stream"

    config.tts.audio_mode = "wav"
    page.reset()
    assert page._tts_audio_mode.currentData() == "wav"


def test_api_page_tts_audio_mode_has_expected_labels():
    _app()
    page = APIPage(APIConfig())

    items = [page._tts_audio_mode.itemText(i) for i in range(page._tts_audio_mode.count())]
    values = [page._tts_audio_mode.itemData(i) for i in range(page._tts_audio_mode.count())]

    assert items == ["自动（推荐）", "PCM流式（低延迟）", "WAV（兼容/调试）"]
    assert values == ["auto", "pcm_stream", "wav"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_config.py tests/test_settings_window.py -q`

Expected: FAIL with errors similar to `AttributeError: 'TTSConfig' object has no attribute 'audio_mode'` or `AttributeError: 'APIPage' object has no attribute '_tts_audio_mode'`.

- [ ] **Step 3: Implement the minimal config and UI changes**

```python
# config/schema.py
class TTSConfig(BaseModel):
    engine: str = "none"
    api_url: str = "http://127.0.0.1:9880"
    audio_mode: str = "auto"
    ref_audio_path: str = ""
    reference_mode: str = "auto"
    prompt_lang: str = "zh"
    output_lang: str = "zh"
    prompt_text: str = ""


# ui/settings/pages/api_page.py
class APIPage(QWidget):
    TTS_AUDIO_MODE_OPTIONS = [
        ("自动（推荐）", "auto"),
        ("PCM流式（低延迟）", "pcm_stream"),
        ("WAV（兼容/调试）", "wav"),
    ]

    def _set_audio_mode(self, audio_mode: str) -> None:
        index = self._tts_audio_mode.findData(audio_mode or "auto")
        if index < 0:
            index = 0
        self._tts_audio_mode.setCurrentIndex(index)
```

```python
# inside APIPage.__init__ after self._tts_url
self._tts_audio_mode = QComboBox()
for label, value in self.TTS_AUDIO_MODE_OPTIONS:
    self._tts_audio_mode.addItem(label, value)
self._set_audio_mode(config.tts.audio_mode)
self._tts_audio_mode.setToolTip("自动优先尝试 PCM 流式，失败时在当前会话回退为 WAV。")
tts_form.addRow("音频模式:", self._tts_audio_mode)

# inside APIPage.apply
self._config.tts.audio_mode = self._tts_audio_mode.currentData()

# inside APIPage.reset
self._set_audio_mode(self._config.tts.audio_mode)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_config.py tests/test_settings_window.py -q`

Expected: PASS with the new config field and settings combo tests green.

- [ ] **Step 5: Commit**

```bash
git add config/schema.py ui/settings/pages/api_page.py tests/test_config.py tests/test_settings_window.py
git commit -m "feat: add tts audio mode setting"
```

## Task 2: Introduce Stream Event Types Without Breaking Legacy Callers

**Files:**
- Create: `tts/types.py`
- Modify: `tts/adapter.py`
- Modify: `tests/test_tts_adapter.py`

- [ ] **Step 1: Write the failing tests for stream types and adapter compatibility**

```python
# tests/test_tts_adapter.py
from tts.adapter import TTSAdapter
from tts.types import TTSAudioFormat, TTSStreamEvent


def test_tts_audio_format_and_event_store_transport_metadata():
    audio_format = TTSAudioFormat(
        transport="pcm_stream",
        sample_rate=32000,
        channels=1,
        sample_width=2,
    )
    event = TTSStreamEvent(kind="start", format=audio_format)

    assert event.kind == "start"
    assert event.format.transport == "pcm_stream"
    assert event.format.sample_rate == 32000


def test_adapter_synthesize_collects_chunk_bytes_from_stream():
    class _FakeAdapter(TTSAdapter):
        def stream_synthesize(self, text: str):
            yield TTSStreamEvent(
                kind="start",
                format=TTSAudioFormat(transport="wav", sample_rate=0, channels=0, sample_width=0),
            )
            yield TTSStreamEvent(kind="chunk", data=b"abc")
            yield TTSStreamEvent(kind="chunk", data=b"def")
            yield TTSStreamEvent(kind="end")

    assert _FakeAdapter().synthesize("hello") == b"abcdef"


def test_adapter_synthesize_returns_none_on_error_event():
    class _FakeAdapter(TTSAdapter):
        def stream_synthesize(self, text: str):
            yield TTSStreamEvent(kind="error", message="boom")

    assert _FakeAdapter().synthesize("hello") is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_tts_adapter.py -q`

Expected: FAIL with `ModuleNotFoundError: No module named 'tts.types'` and `TypeError` around missing `stream_synthesize`.

- [ ] **Step 3: Implement the stream types and compatibility wrapper**

```python
# tts/types.py
from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class TTSAudioFormat:
    transport: Literal["wav", "pcm_stream"]
    sample_rate: int
    channels: int
    sample_width: int


@dataclass(frozen=True)
class TTSStreamEvent:
    kind: Literal["start", "chunk", "end", "error"]
    format: TTSAudioFormat | None = None
    data: bytes | None = None
    message: str = ""


# tts/adapter.py
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
            if event.kind == "chunk" and event.data:
                chunks.append(event.data)
        return b"".join(chunks) if chunks else None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_tts_adapter.py -q`

Expected: PASS for the new stream type tests, while legacy `synthesize()` callers still work.

- [ ] **Step 5: Commit**

```bash
git add tts/types.py tts/adapter.py tests/test_tts_adapter.py
git commit -m "feat: add tts stream event abstractions"
```

## Task 3: Extend `GPTSoVITSAdapter` For Audio Modes, `session_id`, And Auto Fallback

**Files:**
- Modify: `tts/adapters/gptsovits.py`
- Modify: `tests/test_tts_adapter.py`

> 说明：本任务中的 `session_id`、PCM 流式与自动回退示例，仅适用于目标服务端已经显式声明支持对应扩展的情况。若目标服务端未声明支持该扩展，则实现必须优先保留原版显式参考字段路径。

- [ ] **Step 1: Write the failing adapter tests for mode mapping, session reuse, and fallback**

```python
# tests/test_tts_adapter.py
def test_gptsovits_prepare_reference_sends_session_id(monkeypatch):
    calls = []

    class _FakeSession:
        def get(self, url, params=None, timeout=None):
            calls.append(("GET", url, params))
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.text = "ok"
            return mock_resp

        def post(self, *args, **kwargs):
            raise AssertionError("not used")

    monkeypatch.setattr("tts.adapters.gptsovits.requests.Session", lambda: _FakeSession())
    adapter = GPTSoVITSAdapter(
        TTSConfig(engine="gptsovits", api_url="http://fake:9880", ref_audio_path="ref.wav"),
        session_id="sess-1",
    )

    adapter.prepare_reference()
    assert calls[0][2]["session_id"] == "sess-1"


def test_gptsovits_pcm_stream_mode_uses_low_latency_payload(monkeypatch):
    captured = {}

    class _FakeResponse:
        status_code = 200
        headers = {
            "X-Audio-Sample-Rate": "32000",
            "X-Audio-Channels": "1",
            "X-Audio-Sample-Width": "2",
        }

        def iter_content(self, chunk_size=None):
            yield b"\x00\x01"
            yield b"\x02\x03"

    class _FakeSession:
        def get(self, *args, **kwargs):
            raise AssertionError("not used")

        def post(self, url, json=None, timeout=None, stream=None):
            captured["url"] = url
            captured["json"] = json
            captured["stream"] = stream
            return _FakeResponse()

    monkeypatch.setattr("tts.adapters.gptsovits.requests.Session", lambda: _FakeSession())
    adapter = GPTSoVITSAdapter(
        TTSConfig(engine="gptsovits", api_url="http://fake:9880", audio_mode="pcm_stream"),
        session_id="sess-1",
    )

    events = list(adapter.stream_synthesize("你好"))
    assert captured["json"]["media_type"] == "raw"
    assert captured["json"]["streaming_mode"] == 3
    assert captured["json"]["parallel_infer"] is False
    assert captured["json"]["session_id"] == "sess-1"
    assert captured["stream"] is True
    assert [event.kind for event in events] == ["start", "chunk", "chunk", "end"]


def test_gptsovits_auto_mode_retries_as_wav_and_locks_session(monkeypatch):
    calls = []

    class _FakeRawResponse:
        status_code = 409
        text = "streaming mode unsupported"
        headers = {}

        def iter_content(self, chunk_size=None):
            return iter(())

    class _FakeWavResponse:
        status_code = 200
        content = b"wav-bytes"
        headers = {}

        def iter_content(self, chunk_size=None):
            return iter(())

    class _FakeSession:
        def get(self, *args, **kwargs):
            raise AssertionError("not used")

        def post(self, url, json=None, timeout=None, stream=None):
            calls.append(json)
            return _FakeRawResponse() if len(calls) == 1 else _FakeWavResponse()

    monkeypatch.setattr("tts.adapters.gptsovits.requests.Session", lambda: _FakeSession())
    adapter = GPTSoVITSAdapter(
        TTSConfig(engine="gptsovits", api_url="http://fake:9880", audio_mode="auto"),
        session_id="sess-1",
    )

    assert adapter.synthesize("hello") == b"wav-bytes"
    assert calls[0]["media_type"] == "raw"
    assert calls[1]["media_type"] == "wav"
    assert adapter.get_session_audio_mode() == "wav"


def test_gptsovits_without_session_extension_keeps_original_reference_flow(monkeypatch):
    captured = {}

    class _FakeResponse:
        status_code = 200
        content = b"wav-bytes"
        headers = {}

        def iter_content(self, chunk_size=None):
            return iter(())

    class _FakeSession:
        def get(self, *args, **kwargs):
            raise AssertionError("not used")

        def post(self, url, json=None, timeout=None, stream=None):
            captured["json"] = json
            captured["stream"] = stream
            return _FakeResponse()

    monkeypatch.setattr("tts.adapters.gptsovits.requests.Session", lambda: _FakeSession())
    adapter = GPTSoVITSAdapter(
        TTSConfig(engine="gptsovits", api_url="http://fake:9880", audio_mode="wav", ref_audio_path="ref.wav"),
    )

    assert adapter.synthesize("hello") == b"wav-bytes"
    assert "session_id" not in captured["json"]
    assert captured["json"]["media_type"] == "wav"
    assert captured["json"]["streaming_mode"] == 0
    assert captured["stream"] is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_tts_adapter.py -q`

Expected: FAIL with constructor/signature errors such as `TypeError: __init__() got an unexpected keyword argument 'session_id'` or missing `stream_synthesize` / `get_session_audio_mode`.

- [ ] **Step 3: Implement audio mode mapping, stream output, and fallback**

```python
# tts/adapters/gptsovits.py
class GPTSoVITSAdapter(TTSAdapter):
    AUDIO_MODE_AUTO = "auto"
    AUDIO_MODE_PCM_STREAM = "pcm_stream"
    AUDIO_MODE_WAV = "wav"

    def __init__(self, config: TTSConfig, session_id: str | None = None):
        self._api_url = self._normalize_api_url(config.api_url)
        self._session_id = (session_id or "").strip()
        self._audio_mode = self._normalize_audio_mode(config.audio_mode)
        self._session_audio_mode_override: str | None = None

    @classmethod
    def _normalize_audio_mode(cls, audio_mode: str) -> str:
        normalized = (audio_mode or cls.AUDIO_MODE_AUTO).strip().lower()
        if normalized in {cls.AUDIO_MODE_AUTO, cls.AUDIO_MODE_PCM_STREAM, cls.AUDIO_MODE_WAV}:
            return normalized
        return cls.AUDIO_MODE_AUTO

    def get_session_audio_mode(self) -> str:
        return self._session_audio_mode_override or self._audio_mode

    def force_session_audio_mode(self, audio_mode: str) -> None:
        self._session_audio_mode_override = self._normalize_audio_mode(audio_mode)

    def _supports_session_extension(self) -> bool:
        return bool(self._session_id)

    def _effective_audio_mode(self) -> str:
        if self._session_audio_mode_override:
            return self._session_audio_mode_override
        if self._audio_mode == self.AUDIO_MODE_AUTO:
            return self.AUDIO_MODE_PCM_STREAM if self._supports_session_extension() else self.AUDIO_MODE_WAV
        return self._audio_mode

    def _build_audio_payload(self, text: str, include_reference: bool, audio_mode: str) -> dict[str, object]:
        payload: dict[str, object] = {
            "text": text,
            "text_lang": self._output_lang,
        }
        if self._supports_session_extension():
            payload["session_id"] = self._session_id
        if audio_mode == self.AUDIO_MODE_PCM_STREAM:
            payload.update({
                "media_type": "raw",
                "streaming_mode": 3,
                "text_split_method": "cut5",
                "batch_size": 1,
                "parallel_infer": False,
                "split_bucket": False,
                "overlap_length": 2,
                "min_chunk_length": 12,
            })
        else:
            payload.update({
                "media_type": "wav",
                "streaming_mode": 0,
                "text_split_method": "cut5",
                "batch_size": 1,
                "parallel_infer": True,
                "split_bucket": True,
                "overlap_length": 2,
                "min_chunk_length": 16,
            })
        return payload

    def stream_synthesize(self, text: str):
        if self.needs_reference_prepare():
            self.prepare_reference()

        mode = self._effective_audio_mode()
        include_reference = self._should_include_reference()
        yield from self._request_audio_stream(text, include_reference, mode, allow_auto_retry=self._audio_mode == self.AUDIO_MODE_AUTO)
```

```python
# inside GPTSoVITSAdapter
def _request_audio_stream(self, text: str, include_reference: bool, audio_mode: str, allow_auto_retry: bool):
    payload = self._build_audio_payload(text, include_reference, audio_mode)
    try:
        resp = self._session.post(
            self._api_url,
            json=payload,
            timeout=30,
            stream=(audio_mode == self.AUDIO_MODE_PCM_STREAM),
        )
    except Exception as exc:
        if allow_auto_retry and audio_mode == self.AUDIO_MODE_PCM_STREAM:
            yield from self._request_audio_stream(text, include_reference, self.AUDIO_MODE_WAV, allow_auto_retry=False)
            self.force_session_audio_mode(self.AUDIO_MODE_WAV)
            return
        yield TTSStreamEvent(kind="error", message=str(exc))
        return

    if audio_mode == self.AUDIO_MODE_PCM_STREAM and resp.status_code == 200:
        yield TTSStreamEvent(
            kind="start",
            format=TTSAudioFormat(
                transport="pcm_stream",
                sample_rate=int(resp.headers.get("X-Audio-Sample-Rate", "32000")),
                channels=int(resp.headers.get("X-Audio-Channels", "1")),
                sample_width=int(resp.headers.get("X-Audio-Sample-Width", "2")),
            ),
        )
        emitted = False
        for chunk in resp.iter_content(chunk_size=None):
            if not chunk:
                continue
            emitted = True
            yield TTSStreamEvent(kind="chunk", data=chunk)
        if emitted:
            yield TTSStreamEvent(kind="end")
            return

    if audio_mode == self.AUDIO_MODE_WAV and resp.status_code == 200:
        yield TTSStreamEvent(
            kind="start",
            format=TTSAudioFormat(transport="wav", sample_rate=0, channels=0, sample_width=0),
        )
        yield TTSStreamEvent(kind="chunk", data=resp.content)
        yield TTSStreamEvent(kind="end")
        return

    if allow_auto_retry and audio_mode == self.AUDIO_MODE_PCM_STREAM:
        yield from self._request_audio_stream(text, include_reference, self.AUDIO_MODE_WAV, allow_auto_retry=False)
        self.force_session_audio_mode(self.AUDIO_MODE_WAV)
        return

    yield TTSStreamEvent(kind="error", message=f"HTTP {resp.status_code}")
```

- [ ] **Step 4: Run adapter tests to verify they pass**

Run: `python -m pytest tests/test_tts_adapter.py -q`

Expected: PASS with mode mapping, `session_id`, and auto WAV fallback covered.

- [ ] **Step 5: Commit**

```bash
git add tts/adapters/gptsovits.py tests/test_tts_adapter.py
git commit -m "feat: add gptsovits pcm stream modes"
```

## Task 4: Add Dedicated WAV And PCM Playback Backends

**Files:**
- Create: `ui/chat/audio_backends.py`
- Create: `tests/test_audio_backends.py`

- [ ] **Step 1: Write the failing backend tests**

```python
# tests/test_audio_backends.py
from tts.types import TTSAudioFormat
from ui.chat.audio_backends import StreamingAudioBuffer, WavPlaybackBackend, PcmStreamPlaybackBackend


def test_streaming_audio_buffer_reads_appended_bytes_in_order():
    buffer = StreamingAudioBuffer()
    buffer.append_chunk(b"ab")
    buffer.append_chunk(b"cd")

    assert bytes(buffer.readData(4)) == b"abcd"


def test_pcm_backend_marks_audio_as_started_after_first_chunk():
    backend = PcmStreamPlaybackBackend()
    backend.start_stream(TTSAudioFormat(transport="pcm_stream", sample_rate=32000, channels=1, sample_width=2))
    backend.append_chunk(b"\x00\x01")

    assert backend.has_started_playback() is True


def test_wav_backend_buffers_whole_audio_until_end():
    backend = WavPlaybackBackend()
    backend.start_stream(TTSAudioFormat(transport="wav", sample_rate=0, channels=0, sample_width=0))
    backend.append_chunk(b"a")
    backend.append_chunk(b"b")
    backend.finish_stream()

    assert backend.current_payload() == b"ab"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_audio_backends.py -q`

Expected: FAIL with `ModuleNotFoundError: No module named 'ui.chat.audio_backends'`.

- [ ] **Step 3: Implement the backends with injectable Qt dependencies**

```python
# ui/chat/audio_backends.py
from PySide6.QtCore import QByteArray, QBuffer, QIODevice, QObject, Signal
from PySide6.QtMultimedia import QAudioFormat, QAudioOutput, QAudioSink, QMediaPlayer


class StreamingAudioBuffer(QIODevice):
    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._chunks = bytearray()
        self._offset = 0
        self._closed = False
        self.open(QIODevice.OpenModeFlag.ReadOnly)

    def append_chunk(self, data: bytes) -> None:
        self._chunks.extend(data)
        self.readyRead.emit()

    def finish(self) -> None:
        self._closed = True

    def has_pending_data(self) -> bool:
        return self._offset < len(self._chunks)

    def readData(self, maxlen: int):
        if self._offset >= len(self._chunks):
            return b""
        end = min(len(self._chunks), self._offset + maxlen)
        data = bytes(self._chunks[self._offset:end])
        self._offset = end
        return data


class WavPlaybackBackend(QObject):
    playback_finished = Signal()

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._audio_output = QAudioOutput(self)
        self._player = QMediaPlayer(self)
        self._player.setAudioOutput(self._audio_output)
        self._payload = bytearray()
        self._buffer: QBuffer | None = None

    def start_stream(self, audio_format) -> None:
        self._payload.clear()

    def append_chunk(self, data: bytes) -> None:
        self._payload.extend(data)

    def finish_stream(self) -> None:
        self._buffer = QBuffer(self)
        self._buffer.setData(QByteArray(bytes(self._payload)))
        self._buffer.open(QIODevice.OpenModeFlag.ReadOnly)
        self._player.setSourceDevice(self._buffer)
        self._player.play()

    def current_payload(self) -> bytes:
        return bytes(self._payload)


class PcmStreamPlaybackBackend(QObject):
    playback_finished = Signal()

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._buffer: StreamingAudioBuffer | None = None
        self._sink: QAudioSink | None = None
        self._has_started_playback = False

    def start_stream(self, audio_format: TTSAudioFormat) -> None:
        qt_format = QAudioFormat()
        qt_format.setSampleRate(audio_format.sample_rate)
        qt_format.setChannelCount(audio_format.channels)
        qt_format.setSampleFormat(QAudioFormat.SampleFormat.Int16 if audio_format.sample_width == 2 else QAudioFormat.SampleFormat.UInt8)
        self._buffer = StreamingAudioBuffer(self)
        self._sink = QAudioSink(qt_format, self)
        self._sink.start(self._buffer)

    def append_chunk(self, data: bytes) -> None:
        if self._buffer is None:
            raise RuntimeError("PCM stream not started")
        self._buffer.append_chunk(data)
        self._has_started_playback = self._has_started_playback or bool(data)

    def finish_stream(self) -> None:
        if self._buffer is not None:
            self._buffer.finish()

    def has_started_playback(self) -> bool:
        return self._has_started_playback
```

- [ ] **Step 4: Run backend tests to verify they pass**

Run: `python -m pytest tests/test_audio_backends.py -q`

Expected: PASS for buffer ordering, WAV aggregation, and PCM “first chunk means started” behavior.

- [ ] **Step 5: Commit**

```bash
git add ui/chat/audio_backends.py tests/test_audio_backends.py
git commit -m "feat: add chat audio playback backends"
```

## Task 5: Upgrade `ChatWindow` To Consume Stream Events And Manage Session-Level Fallback

**Files:**
- Modify: `ui/chat/window.py`
- Modify: `tests/test_chat_tts_flow.py`

- [ ] **Step 1: Write the failing chat window tests for stream event ordering and fallback**

```python
# tests/test_chat_tts_flow.py
from tts.types import TTSAudioFormat, TTSStreamEvent


def test_handle_tts_stream_event_starts_pcm_backend_on_first_chunk(chat_window, monkeypatch):
    starts = []
    chunks = []
    monkeypatch.setattr(chat_window, "_start_segment_backend", lambda key, audio_format: starts.append((key, audio_format.transport)), raising=False)
    monkeypatch.setattr(chat_window, "_append_segment_chunk", lambda key, data: chunks.append((key, data)), raising=False)

    key = (chat_window._current_utterance_id, 0)
    chat_window._handle_tts_stream_event(
        key[0],
        key[1],
        TTSStreamEvent(kind="start", format=TTSAudioFormat(transport="pcm_stream", sample_rate=32000, channels=1, sample_width=2)),
    )
    chat_window._handle_tts_stream_event(key[0], key[1], TTSStreamEvent(kind="chunk", data=b"\x00\x01"))

    assert starts == [(key, "pcm_stream")]
    assert chunks == [(key, b"\x00\x01")]


def test_next_segment_waits_until_current_segment_finishes(chat_window):
    key0 = (chat_window._current_utterance_id, 0)
    key1 = (chat_window._current_utterance_id, 1)

    chat_window._segment_events[key1] = [TTSStreamEvent(kind="chunk", data=b"later")]
    chat_window._segment_states[key0] = "streaming"
    chat_window._segment_states[key1] = "pending"

    chat_window._advance_ready_segments()

    assert chat_window._active_segment_key == key0


def test_pcm_failure_before_audio_starts_forces_session_wav(chat_window):
    adapter = chat_window._tts_adapter
    key = (chat_window._current_utterance_id, 0)

    chat_window._handle_tts_stream_event(key[0], key[1], TTSStreamEvent(kind="error", message="first chunk timeout"))

    assert adapter.get_session_audio_mode() == "wav"


def test_begin_new_tts_turn_clears_segment_stream_state(chat_window):
    chat_window._segment_states[(chat_window._current_utterance_id, 0)] = "streaming"
    chat_window._segment_events[(chat_window._current_utterance_id, 0)] = [TTSStreamEvent(kind="chunk", data=b"a")]

    chat_window._begin_new_tts_turn()

    assert chat_window._segment_states == {}
    assert chat_window._segment_events == {}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_chat_tts_flow.py -q`

Expected: FAIL with missing attributes such as `_handle_tts_stream_event`, `_segment_events`, `_segment_states`, or `_start_segment_backend`.

- [ ] **Step 3: Implement session IDs, stream workers, and dual-backend playback**

```python
# ui/chat/window.py
import uuid
from tts.types import TTSStreamEvent
from ui.chat.audio_backends import PcmStreamPlaybackBackend, WavPlaybackBackend


class TTSWorker(QThread):
    event_ready = Signal(int, int, object)

    def run(self):
        if self._adapter is None:
            return
        for event in self._adapter.stream_synthesize(self._text):
            self.event_ready.emit(self._utterance_id, self._segment_id, event)


class ChatWindow(QWidget):
    def __init__(
        self,
        config: LLMConfig,
        character_dir: Path | None = None,
        tool_registry: ToolRegistry | None = None,
        memory_store=None,
        user_id: str | None = None,
        settings_window_factory=None,
        agent_config=None,
        tts_config: TTSConfig | None = None,
    ):
        # `session_id` 只是显式扩展能力的运行态，不得被视为默认主线前置条件。
        self._tts_session_id = uuid.uuid4().hex
        self._segment_states: dict[tuple[int, int], str] = {}
        self._segment_events: dict[tuple[int, int], list[TTSStreamEvent]] = {}
        self._segment_backends: dict[tuple[int, int], object] = {}
        self._active_segment_key: tuple[int, int] | None = None
        self._tts_adapter = self._create_tts_adapter(tts_config, self._tts_session_id)

    @staticmethod
    def _create_tts_adapter(tts_config: TTSConfig | None, session_id: str | None = None):
        if tts_config is None:
            return None
        if tts_config.engine == "gptsovits":
            return GPTSoVITSAdapter(tts_config, session_id=session_id)
        return None

    def _start_tts_worker(self, utterance_id: int, segment_id: int, text: str) -> None:
        worker = TTSWorker(self._tts_adapter, utterance_id, segment_id, text)
        worker.event_ready.connect(self._handle_tts_stream_event, Qt.ConnectionType.QueuedConnection)
        worker.finished.connect(lambda: self._on_tts_worker_finished(worker))
        self._active_tts_workers.append(worker)
        worker.start()
```

```python
# ui/chat/window.py
def _handle_tts_stream_event(self, utterance_id: int, segment_id: int, event: TTSStreamEvent) -> None:
    if utterance_id != self._current_utterance_id:
        return
    key = (utterance_id, segment_id)
    self._segment_events.setdefault(key, []).append(event)
    self._segment_states.setdefault(key, "pending")
    self._advance_ready_segments()


def _advance_ready_segments(self) -> None:
    if self._active_segment_key is None:
        self._active_segment_key = (self._current_utterance_id, self._next_play_id)
    key = self._active_segment_key
    if key not in self._segment_events:
        return
    for event in list(self._segment_events[key]):
        if event.kind == "start" and event.format is not None:
            self._start_segment_backend(key, event.format)
            self._segment_states[key] = "streaming"
        elif event.kind == "chunk" and event.data:
            self._append_segment_chunk(key, event.data)
        elif event.kind == "end":
            self._finish_segment_backend(key)
        elif event.kind == "error":
            self._fail_segment(key, event.message)
        self._segment_events[key].pop(0)


def _fail_segment(self, key: tuple[int, int], message: str) -> None:
    adapter = self._tts_adapter
    if adapter is not None and hasattr(adapter, "force_session_audio_mode"):
        adapter.force_session_audio_mode("wav")
    print(f"[TTS] segment {key[1]} failed: {message}")
    self._segment_states[key] = "failed"
    self._next_play_id += 1
    self._active_segment_key = None
    self._advance_ready_segments()


def _begin_new_tts_turn(self) -> None:
    self._current_utterance_id += 1
    self._streamed_assistant_text = ""
    self._tts_committed_text = ""
    self._tts_pending_buffer = ""
    self._next_segment_id = 0
    self._next_play_id = 0
    self._segment_states.clear()
    self._segment_events.clear()
    self._segment_backends.clear()
    self._active_segment_key = None
```

- [ ] **Step 4: Run focused and full chat TTS tests**

Run: `python -m pytest tests/test_chat_tts_flow.py -q`

Expected: PASS with existing句级切分测试仍然绿色，并新增流式状态机行为测试通过。

- [ ] **Step 5: Commit**

```bash
git add ui/chat/window.py tests/test_chat_tts_flow.py
git commit -m "feat: add streamed pcm playback flow"
```

## Task 6: Sync Docs And Run Full Verification

**Files:**
- Modify: `CLAUDE.md`
- Modify: `docs/README.md`
- Modify: `docs/architecture.md`
- Modify: `docs/development.md`
- Verify: `docs/superpowers/specs/2026-05-23-tts-pcm-design.md`
- Verify: `docs/superpowers/plans/2026-05-23-tts-pcm-implementation.md`

- [ ] **Step 1: Write the failing documentation assertions as a checklist**

```text
- CLAUDE.md 必须写明 TTS 新增 audio_mode、session_id 会话化、PCM 流式播放与自动 WAV 回退
- docs/README.md 必须更新“当前进度”里的 TTS 能力概述
- docs/architecture.md 必须补充 tts/types.py、ui/chat/audio_backends.py 和双播放后端主流程
- docs/development.md 必须把 audio_mode、session_id、PCM 播放后端测试加入 TTS 回归项
- 所有文档必须明确“原版兼容优先、扩展能力显式触发”，不得写成为了桌宠端而改写原版默认行为
- 若保留历史示例，必须明确它们受 `docs/service-tts-compatibility.md` 约束，不能被理解成新的默认逻辑主线
```

- [ ] **Step 2: Run the verification commands before editing docs**

Run: `python -m pytest tests/test_config.py tests/test_settings_window.py tests/test_tts_adapter.py tests/test_audio_backends.py tests/test_chat_tts_flow.py -q`

Expected: PASS. If this fails, do not edit docs yet; return to the failing task and fix the implementation first.

- [ ] **Step 3: Update the docs with the final shipped behavior**

```markdown
# CLAUDE.md
- 句级增量 TTS 播报接入：支持 `audio_mode=auto/pcm_stream/wav`
- ChatWindow 在窗口生命周期内生成 TTS `session_id`，用于 GPT-SoVITS speaker 会话化
- `auto` 模式优先请求 PCM 流式，若流式失败则在当前聊天会话内锁定为 WAV

# docs/architecture.md
- `tts/types.py`
  TTS 流式事件与音频格式模型
- `ui/chat/audio_backends.py`
  WAV 播放后端与 PCM 流式播放后端
- 对话主流程新增：
  → GPT-SoVITS 依据 `audio_mode` 返回 WAV 或 PCM chunk stream
  → ChatWindow 按句段顺序驱动 `QMediaPlayer` 或 `QAudioSink`

# docs/development.md
- TTS 相关改动优先覆盖：
  - `audio_mode` 持久化与设置页 apply/reset
  - `session_id` 对 `/set_refer_audio` 与 `/tts` 的透传
  - PCM 首个 chunk 到达即播、句段有序播放、失败后会话级 WAV 回退
```

- [ ] **Step 4: Run all required verification commands**

Run these commands in order:

```bash
python -m pytest tests/test_config.py tests/test_settings_window.py tests/test_tts_adapter.py tests/test_audio_backends.py tests/test_chat_tts_flow.py -q
python -m pytest tests/ -q
```

Expected:

- First command: PASS on the focused TTS/config regression suite
- Second command: PASS on the full repository test suite

- [ ] **Step 5: Commit**

```bash
git add CLAUDE.md docs/README.md docs/architecture.md docs/development.md
git commit -m "docs: document tts pcm streaming mode"
```

## Self-Review

- Spec coverage:
  - 设置页 `audio_mode`：Task 1
  - 流式事件抽象：Task 2
  - `session_id`、模式映射、自动 WAV 回退：Task 3
  - 双播放后端与 PCM 持续喂数据：Task 4
  - 聊天窗句段状态机、首包即播、会话级回退：Task 5
  - 文档与全量测试：Task 6
- Placeholder scan:
  - 未使用占位词、延后实现提示或跨任务引用式说明
  - 每个代码步骤都给出了具体测试或实现片段
- Type consistency:
  - `TTSStreamEvent`, `TTSAudioFormat`, `stream_synthesize()`, `force_session_audio_mode()`, `get_session_audio_mode()` 在任务之间保持同名
