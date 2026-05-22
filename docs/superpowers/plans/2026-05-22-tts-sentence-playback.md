# TTS 句级增量播报 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
> **Status:** 计划已写完，代码尚未开始。

**Goal:** 为聊天窗接入基于句号级切分的 GPT-SoVITS 自动播报，在流式出字过程中尽早合成并按句序播放语音。

**Architecture:** 保持 `LLMManager` 和 `AgentManager` 不变，在 `ChatWindow` 内增加句级切分、片段调度和播放顺序控制；`SettingsWindow` 只负责透传 TTS 配置，`tts/adapters/gptsovits.py` 负责 HTTP 调用与基础日志。测试覆盖切分规则、顺序约束、旧轮失效和失败容错。

**Tech Stack:** Python, PySide6, pytest, requests

---

### Task 1: 补齐 TTS 适配器与启动透传测试

**Files:**
- Modify: `tests/test_tts_adapter.py`
- Create: `tests/test_chat_tts_flow.py`
- Modify: `ui/settings/window.py`

- [ ] **Step 1: 写出失败测试，锁定适配器和启动透传行为**

```python
from types import SimpleNamespace

from config.schema import TTSConfig
from ui.settings.window import SettingsWindow


def test_gptsovits_synthesize_logs_and_returns_none_on_http_error(monkeypatch, capsys):
    from tts.adapters.gptsovits import GPTSoVITSAdapter

    class MockResp:
        status_code = 500
        content = b""

    monkeypatch.setattr("tts.adapters.gptsovits.requests.post", lambda *a, **kw: MockResp())

    adapter = GPTSoVITSAdapter(TTSConfig(engine="gptsovits", api_url="http://fake:9880"))
    assert adapter.synthesize("你好") is None

    captured = capsys.readouterr()
    assert "500" in captured.out


def test_launch_chat_passes_tts_config(monkeypatch, qtbot):
    captured = {}

    class DummyChatWindow:
        def __init__(self, llm_config, **kwargs):
            captured["llm"] = llm_config
            captured["tts"] = kwargs.get("tts_config")

        def show(self):
            return None

        def set_memory_store(self, memory_store):
            return None

    monkeypatch.setattr("ui.settings.window.ChatWindow", DummyChatWindow)
    monkeypatch.setattr("ui.settings.window.PluginHost", lambda *_: SimpleNamespace(load=lambda: None))
    monkeypatch.setattr("ui.settings.window.MCPHost", lambda *_: SimpleNamespace(connect_all=lambda: None))
    monkeypatch.setattr("ui.settings.window.ToolRegistry", lambda **_: SimpleNamespace())

    class DummyLoader:
        def __init__(self, *_args, **_kwargs):
            self.memory_ready = SimpleNamespace(connect=lambda *_: None)
            self.memory_failed = SimpleNamespace(connect=lambda *_: None)

        def start(self):
            return None

    monkeypatch.setattr("ui.settings.window.MemoryLoaderThread", DummyLoader)

    window = SettingsWindow()
    qtbot.addWidget(window)
    window._launch_chat()

    assert captured["tts"] == window._config.api.tts
```

- [ ] **Step 2: 运行测试，确认按预期失败**

Run: `python -m pytest tests/test_tts_adapter.py tests/test_chat_tts_flow.py -q`
Expected: FAIL，原因是当前没有日志断言支持，且 `ChatWindow` 尚未接收 `tts_config`

- [ ] **Step 3: 写最小实现，让适配器与启动透传通过**

```python
# ui/settings/window.py
self._chat_window = ChatWindow(
    self._config.api.llm,
    character_dir=char_dir,
    tool_registry=tool_registry,
    memory_store=None,
    user_id=self._config.memory.user_id,
    settings_window_factory=lambda: self,
    agent_config=self._config.agent,
    tts_config=self._config.api.tts,
)


# tts/adapters/gptsovits.py
if resp.status_code == 200:
    return resp.content
print(f"[TTS] GPT-SoVITS returned HTTP {resp.status_code}")
return None
```

- [ ] **Step 4: 运行测试，确认通过**

Run: `python -m pytest tests/test_tts_adapter.py tests/test_chat_tts_flow.py -q`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add tests/test_tts_adapter.py tests/test_chat_tts_flow.py ui/settings/window.py tts/adapters/gptsovits.py
git commit -m "test: cover tts adapter and launch wiring"
```

### Task 2: 先用失败测试锁定句级切分规则

**Files:**
- Modify: `tests/test_chat_tts_flow.py`
- Modify: `ui/chat/window.py`

- [ ] **Step 1: 写出句级切分失败测试**

```python
from llm.text_processor import ProcessedText


def test_chunked_output_enqueues_sentence_when_period_arrives(chat_window):
    chat_window._on_chunk(ProcessedText(clean_text="第一句", emotion=None))
    assert chat_window._queued_texts == []

    chat_window._on_chunk(ProcessedText(clean_text="第一句。第二", emotion=None))
    assert chat_window._queued_texts == ["第一句。"]


def test_comma_does_not_split_sentence(chat_window):
    chat_window._on_chunk(ProcessedText(clean_text="你好，世界", emotion=None))
    assert chat_window._queued_texts == []


def test_done_flushes_tail_without_terminal_punctuation(chat_window):
    chat_window._on_chunk(ProcessedText(clean_text="没有句号的尾巴", emotion=None))
    chat_window._on_llm_done()
    assert chat_window._queued_texts == ["没有句号的尾巴"]
```

- [ ] **Step 2: 运行测试，确认按预期失败**

Run: `python -m pytest tests/test_chat_tts_flow.py -q`
Expected: FAIL，原因是当前 `ChatWindow` 没有切分缓冲和队列状态

- [ ] **Step 3: 写最小实现，补齐切分缓冲与 flush**

```python
SENTENCE_ENDINGS = "。！？；\n"

def _extract_tts_segments(self, flush: bool = False) -> list[str]:
    segments = []
    while True:
        cut_index = self._find_sentence_break(self._tts_pending_buffer)
        if cut_index < 0:
            break
        segment = self._tts_pending_buffer[:cut_index].strip()
        self._tts_pending_buffer = self._tts_pending_buffer[cut_index:]
        if segment:
            segments.append(segment)
    if flush and self._tts_pending_buffer.strip():
        segments.append(self._tts_pending_buffer.strip())
        self._tts_pending_buffer = ""
    return segments
```

- [ ] **Step 4: 运行测试，确认通过**

Run: `python -m pytest tests/test_chat_tts_flow.py -q`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add tests/test_chat_tts_flow.py ui/chat/window.py
git commit -m "test: cover sentence-level tts segmentation"
```

### Task 3: 用失败测试锁定顺序播放和旧轮失效

**Files:**
- Modify: `tests/test_chat_tts_flow.py`
- Modify: `ui/chat/window.py`

- [ ] **Step 1: 写出顺序与失效失败测试**

```python
def test_segment_results_play_in_segment_order(chat_window):
    chat_window._current_utterance_id = 1
    chat_window._next_play_id = 0
    chat_window._segment_results[(1, 1)] = b"second"
    chat_window._segment_results[(1, 0)] = b"first"

    chat_window._drain_ready_audio()

    assert chat_window._played_audio == [b"first", b"second"]


def test_new_user_turn_invalidates_old_tts_results(chat_window):
    old_id = chat_window._current_utterance_id
    chat_window._begin_new_tts_turn()
    new_id = chat_window._current_utterance_id

    chat_window._handle_tts_result(old_id, 0, b"old")
    chat_window._handle_tts_result(new_id, 0, b"new")

    assert chat_window._played_audio == [b"new"]
```

- [ ] **Step 2: 运行测试，确认按预期失败**

Run: `python -m pytest tests/test_chat_tts_flow.py -q`
Expected: FAIL，原因是当前没有按轮次/片段顺序管理结果

- [ ] **Step 3: 写最小实现，补齐 `utterance_id`、`segment_id` 和顺序 drain**

```python
def _begin_new_tts_turn(self) -> None:
    self._current_utterance_id += 1
    self._next_segment_id = 0
    self._next_play_id = 0
    self._segment_results.clear()


def _handle_tts_result(self, utterance_id: int, segment_id: int, audio: bytes | None) -> None:
    if utterance_id != self._current_utterance_id or not audio:
        return
    self._segment_results[(utterance_id, segment_id)] = audio
    self._drain_ready_audio()


def _drain_ready_audio(self) -> None:
    while True:
        key = (self._current_utterance_id, self._next_play_id)
        audio = self._segment_results.pop(key, None)
        if audio is None:
            break
        self._play_audio_bytes(audio)
        self._next_play_id += 1
```

- [ ] **Step 4: 运行测试，确认通过**

Run: `python -m pytest tests/test_chat_tts_flow.py -q`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add tests/test_chat_tts_flow.py ui/chat/window.py
git commit -m "test: cover tts ordering and turn invalidation"
```

### Task 4: 用失败测试锁定 TTS 线程与容错行为

**Files:**
- Modify: `tests/test_chat_tts_flow.py`
- Modify: `ui/chat/window.py`

- [ ] **Step 1: 写出 TTS 触发与失败容错测试**

```python
def test_sentence_segment_is_sent_to_tts_worker(chat_window):
    chat_window._on_chunk(ProcessedText(clean_text="你好。", emotion=None))
    assert chat_window._started_segments == [(chat_window._current_utterance_id, 0, "你好。")]


def test_tts_failure_does_not_break_following_segments(chat_window):
    chat_window._handle_tts_result(chat_window._current_utterance_id, 0, None)
    chat_window._handle_tts_result(chat_window._current_utterance_id, 1, b"next")
    assert chat_window._played_audio == []

    chat_window._segment_results[(chat_window._current_utterance_id, 0)] = b"first"
    chat_window._drain_ready_audio()
    assert chat_window._played_audio == [b"first", b"next"]
```

- [ ] **Step 2: 运行测试，确认按预期失败**

Run: `python -m pytest tests/test_chat_tts_flow.py -q`
Expected: FAIL，原因是当前没有 TTS worker 启动点和失败占位推进逻辑

- [ ] **Step 3: 写最小实现，补齐 worker 触发与失败占位**

```python
def _enqueue_tts_segment(self, text: str) -> None:
    segment_id = self._next_segment_id
    self._next_segment_id += 1
    self._start_tts_worker(self._current_utterance_id, segment_id, text)


def _handle_tts_result(self, utterance_id: int, segment_id: int, audio: bytes | None) -> None:
    if utterance_id != self._current_utterance_id:
        return
    self._segment_results[(utterance_id, segment_id)] = audio or b""
    self._drain_ready_audio()


def _drain_ready_audio(self) -> None:
    while True:
        key = (self._current_utterance_id, self._next_play_id)
        if key not in self._segment_results:
            break
        audio = self._segment_results.pop(key)
        if audio:
            self._play_audio_bytes(audio)
        self._next_play_id += 1
```

- [ ] **Step 4: 运行测试，确认通过**

Run: `python -m pytest tests/test_chat_tts_flow.py -q`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add tests/test_chat_tts_flow.py ui/chat/window.py
git commit -m "feat: queue sentence tts synthesis"
```

### Task 5: 接入真实播放实现并更新文档

**Files:**
- Modify: `ui/chat/window.py`
- Modify: `CLAUDE.md`
- Modify: `docs/architecture.md`
- Modify: `docs/development.md`

- [ ] **Step 1: 写出播放适配失败测试**

```python
def test_play_audio_bytes_uses_player_backend(chat_window):
    payload = b"fake-audio"
    chat_window._play_audio_bytes(payload)
    assert chat_window._player_payloads == [payload]
```

- [ ] **Step 2: 运行测试，确认按预期失败**

Run: `python -m pytest tests/test_chat_tts_flow.py -q`
Expected: FAIL，原因是当前没有播放器后端封装

- [ ] **Step 3: 写最小实现，补齐播放器后端和文档同步**

```python
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtCore import QBuffer, QByteArray, QIODevice

def _ensure_audio_backend(self) -> None:
    if self._audio_player is not None:
        return
    self._audio_output = QAudioOutput(self)
    self._audio_player = QMediaPlayer(self)
    self._audio_player.setAudioOutput(self._audio_output)

def _play_audio_bytes(self, audio: bytes) -> None:
    self._ensure_audio_backend()
    self._audio_buffer = QBuffer(self)
    self._audio_buffer.setData(QByteArray(audio))
    self._audio_buffer.open(QIODevice.OpenModeFlag.ReadOnly)
    self._audio_player.setSourceDevice(self._audio_buffer)
    self._audio_player.play()
```

- [ ] **Step 4: 运行测试，确认通过**

Run: `python -m pytest tests/test_chat_tts_flow.py tests/test_tts_adapter.py -q`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add ui/chat/window.py CLAUDE.md docs/architecture.md docs/development.md tests/test_chat_tts_flow.py tests/test_tts_adapter.py
git commit -m "feat: add sentence-level tts playback"
```
