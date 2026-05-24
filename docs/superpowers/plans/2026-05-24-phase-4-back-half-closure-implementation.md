# Phase 4 后半段收口 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不回退已完成 Phase 4 前半段实现的前提下，把 EventBus 线程治理、TTS 有界流水线、以及 Phase 4 文档与验证收口到可对照 spec 验收的状态。

**Architecture:** 当前仓库已经具备 `SessionContext`、基础 EventBus 线程安全、有限 PCM 读超时、以及 TTS worker 上限。后半段收口不再重复这些基础实现，而是围绕三个缺口推进：一是补 UI 主线程桥与日志节流，二是把 TTS 的句段生命周期、取消语义、总超时和队列上限补齐，三是用回归测试和文档把“基础实现”推进到“可交付状态”。

**Tech Stack:** Python、PySide6、pytest、Qt Signal/Slot、requests、现有 `AgentManager` / `ChatWindow` / `GPTSoVITSAdapter`。

---

## 与旧计划的映射关系

本计划是对 [Phase 4 核心链路实施计划](./2026-05-24-phase-4-core-chain-implementation.md) 的后半段续篇，只覆盖“未完成 + 已部分完成但未收口”的部分：

- 旧计划 `任务 5` → 本计划 `任务 1-2`
- 旧计划 `任务 6-7` → 本计划 `任务 3-4`
- 旧计划 `任务 8` → 本计划 `任务 5`

说明：

- 旧计划 `任务 0-4` 已在当前分支完成，不再重复。
- `core/event_bus.py` 的线程安全快照发布、`tts/adapters/gptsovits.py` 的有限 PCM 读超时、`ui/chat/window.py` 的基础 worker 上限已经落地；本计划只负责把这些“基础实现”推进到 spec 收口状态。

## 文件结构

### 新增文件

- `core/ui_event_bridge.py`
  Qt 主线程桥与日志批量刷新入口，负责把后台事件回送到主线程，并为日志类事件提供缓冲与节流。
- `ui/chat/tts_pipeline.py`
  定义句段状态模型、状态推进规则、队列上限和总超时辅助逻辑，避免 `ui/chat/window.py` 继续膨胀。
- `tests/test_agent_page_events.py`
  覆盖 Agent 日志页通过桥接消费事件、批量刷日志、关闭时退订等行为。
- `tests/test_tts_pipeline.py`
  覆盖句段状态流转、取消语义、总超时和队列上限。

### 需要修改的现有文件

- `config/schema.py`
  增加 `EventBusRuntimeConfig`，并补齐 TTS 运行时配置的实际使用范围。
- `ui/settings/pages/agent_page.py`
  当前直接订阅全局 `event_bus` 并在回调里更新 UI，需要改成“后台线程只发事件，UI 通过主线程桥消费”，同时补退订与日志缓冲。
- `core/event_bus.py`
  保留现有线程安全快照发布，实现少量辅助接口（例如 handler 注册表维护），但不重做为复杂总线。
- `ui/chat/window.py`
  改为依赖 `ui/chat/tts_pipeline.py` 管理句段状态、总超时、取消与队列上限。
- `tts/adapters/gptsovits.py`
  继续沿用现有有限读超时，实现和 TTS 总超时 / WAV 回退一致的失败语义。
- `tests/test_event_bus.py`
  覆盖桥接与日志缓冲行为。
- `tests/test_chat_tts_flow.py`
  聚焦 `ChatWindow` 与 `TTSPipelineController` 的协同行为。
- `tests/test_tts_adapter.py`
  覆盖 PCM 总超时、超时后事件语义和 WAV 回退边界。
- `tests/test_config_agent.py`
  覆盖 `event_bus_runtime` 新配置默认值。
- `docs/architecture.md`
- `docs/development.md`
- `docs/README.md`

---

## 任务 1：补齐 EventBus 运行时配置与主线程桥原语

**Files:**
- Create: `core/ui_event_bridge.py`
- Modify: `config/schema.py`
- Modify: `tests/test_config_agent.py`
- Modify: `tests/test_event_bus.py`

- [ ] **Step 1: 先写失败测试，锁定 EventBus 运行时配置必须进入配置层**

```python
from config.schema import AgentConfig


def test_agent_config_exposes_event_bus_runtime_settings():
    cfg = AgentConfig()

    assert hasattr(cfg, "event_bus_runtime")
    assert hasattr(cfg.event_bus_runtime, "log_max_buffer")
    assert hasattr(cfg.event_bus_runtime, "log_flush_interval_ms")
    assert hasattr(cfg.event_bus_runtime, "ui_dispatch_throttle_ms")
```

- [ ] **Step 2: 运行测试，确认当前失败**

运行：

`python -m pytest tests/test_config_agent.py -k event_bus_runtime_settings -v`

预期：

- 失败，因为 `AgentConfig` 还没有 `event_bus_runtime`。

- [ ] **Step 3: 写失败测试，锁定主线程桥的批量日志刷新行为**

```python
from core.ui_event_bridge import UIEventBridge


def test_ui_event_bridge_flushes_log_batch_in_order(qtbot):
    bridge = UIEventBridge(log_max_buffer=4, log_flush_interval_ms=10, ui_dispatch_throttle_ms=0)
    received = []
    bridge.log_batch_ready.connect(lambda batch: received.extend(batch))

    bridge.enqueue_log("a")
    bridge.enqueue_log("b")
    bridge.flush_logs()

    assert received == ["a", "b"]
```

- [ ] **Step 4: 运行测试，确认当前失败**

运行：

`python -m pytest tests/test_event_bus.py -k flushes_log_batch_in_order -v`

预期：

- 失败，因为 `core.ui_event_bridge` 尚不存在。

- [ ] **Step 5: 写最小实现，先把配置和桥原语建起来**

```python
# config/schema.py
class EventBusRuntimeConfig(BaseModel):
    log_max_buffer: int = 200
    log_flush_interval_ms: int = 80
    ui_dispatch_throttle_ms: int = 0


class AgentConfig(BaseModel):
    ...
    event_bus_runtime: EventBusRuntimeConfig = EventBusRuntimeConfig()
```

```python
# core/ui_event_bridge.py
from __future__ import annotations

from collections import deque

from PySide6.QtCore import QObject, QTimer, Signal


class UIEventBridge(QObject):
    ui_event_ready = Signal(str, object)
    log_batch_ready = Signal(object)

    def __init__(self, log_max_buffer: int, log_flush_interval_ms: int, ui_dispatch_throttle_ms: int, parent=None):
        super().__init__(parent)
        self._log_buffer = deque(maxlen=log_max_buffer)
        self._log_timer = QTimer(self)
        self._log_timer.setSingleShot(True)
        self._log_timer.setInterval(log_flush_interval_ms)
        self._log_timer.timeout.connect(self.flush_logs)

    def dispatch_ui_event(self, event_name: str, payload: object) -> None:
        self.ui_event_ready.emit(event_name, payload)

    def enqueue_log(self, text: str) -> None:
        self._log_buffer.append(text)
        if not self._log_timer.isActive():
            self._log_timer.start()

    def flush_logs(self) -> None:
        if not self._log_buffer:
            return
        batch = list(self._log_buffer)
        self._log_buffer.clear()
        self.log_batch_ready.emit(batch)
```

- [ ] **Step 6: 运行定向测试，确认通过**

运行：

`python -m pytest tests/test_config_agent.py -k event_bus_runtime_settings -v`

`python -m pytest tests/test_event_bus.py -k flushes_log_batch_in_order -v`

预期：

- 通过。

- [ ] **Step 7: 提交这一小步**

```bash
git add config/schema.py core/ui_event_bridge.py tests/test_config_agent.py tests/test_event_bus.py
git commit -m "feat(core): add event bus runtime bridge primitives"
```

---

## 任务 2：让 Agent 日志页通过主线程桥消费事件，并补退订与节流

**Files:**
- Modify: `ui/settings/pages/agent_page.py`
- Modify: `core/event_bus.py`
- Create: `tests/test_agent_page_events.py`
- Modify: `tests/test_agent_log_events.py`

- [ ] **Step 1: 先写失败测试，锁定 AgentPage 关闭时必须退订**

```python
from core.event_bus import EventBus
from ui.settings.pages.agent_page import AgentPage


def test_agent_page_teardown_unsubscribes_all_handlers(qtbot):
    bus = EventBus()
    page = AgentPage(event_bus_instance=bus)
    qtbot.addWidget(page)

    assert len(bus._handlers) > 0

    page._teardown_event_subscription()

    assert all(not handlers for handlers in bus._handlers.values())
```

- [ ] **Step 2: 运行测试，确认当前失败**

运行：

`python -m pytest tests/test_agent_page_events.py -k teardown_unsubscribes_all_handlers -v`

预期：

- 失败，因为 `AgentPage` 还没有 `_teardown_event_subscription()`，也没有注入式 `event_bus_instance`。

- [ ] **Step 3: 再写失败测试，锁定日志通过桥批量刷入 UI**

```python
from core.ui_event_bridge import UIEventBridge
from ui.settings.pages.agent_page import AgentPage


def test_agent_page_appends_log_batch_from_bridge(qtbot):
    page = AgentPage()
    qtbot.addWidget(page)

    page._handle_log_batch(["a", "b"])

    assert len(page._log_entries) == 2
```

- [ ] **Step 4: 运行测试，确认当前失败**

运行：

`python -m pytest tests/test_agent_page_events.py -k appends_log_batch_from_bridge -v`

预期：

- 失败，因为页面目前只有单条 `_append_log()` 路径。

- [ ] **Step 5: 写最小实现，把 UI 监听路径改到桥上**

```python
# ui/settings/pages/agent_page.py（概念性结构）
class AgentPage(QWidget):
    def __init__(self, ..., event_bus_instance=None):
        ...
        self._event_bus = event_bus_instance or event_bus
        self._ui_bridge = UIEventBridge(
            log_max_buffer=self._config.event_bus_runtime.log_max_buffer,
            log_flush_interval_ms=self._config.event_bus_runtime.log_flush_interval_ms,
            ui_dispatch_throttle_ms=self._config.event_bus_runtime.ui_dispatch_throttle_ms,
            parent=self,
        )
        self._subscriptions: list[tuple[str, object]] = []

    def _setup_event_subscription(self):
        self._ui_bridge.log_batch_ready.connect(self._handle_log_batch)
        self._ui_bridge.ui_event_ready.connect(self._dispatch_ui_event, Qt.ConnectionType.QueuedConnection)
        self._subscribe(AgentEvents.PLANNER_DECIDED, self._handle_planner_event)
        ...

    def _subscribe(self, event_name: str, handler):
        self._event_bus.subscribe(event_name, handler)
        self._subscriptions.append((event_name, handler))

    def _teardown_event_subscription(self):
        for event_name, handler in self._subscriptions:
            self._event_bus.unsubscribe(event_name, handler)
        self._subscriptions.clear()

    def _handle_log_batch(self, batch: list[str]) -> None:
        for text in batch:
            self._append_log(text)
```

- [ ] **Step 6: 运行定向测试，确认通过**

运行：

`python -m pytest tests/test_agent_page_events.py -q`

预期：

- 通过。

- [ ] **Step 7: 补一个已有行为回归，确认 AgentManager 事件仍然可被普通 EventBus 订阅者消费**

运行：

`python -m pytest tests/test_agent_log_events.py -q`

预期：

- 通过，说明 `AgentManager -> EventBus` 的普通发布路径没有被 UI bridge 破坏。

- [ ] **Step 8: 提交这一小步**

```bash
git add ui/settings/pages/agent_page.py core/event_bus.py tests/test_agent_page_events.py tests/test_agent_log_events.py
git commit -m "refactor(ui): bridge agent log events to main thread"
```

---

## 任务 3：抽出 TTS 句段状态模型，补齐取消语义与总超时

**Files:**
- Create: `ui/chat/tts_pipeline.py`
- Create: `tests/test_tts_pipeline.py`
- Modify: `ui/chat/window.py`
- Modify: `tests/test_chat_tts_flow.py`

- [ ] **Step 1: 先写失败测试，锁定句段状态流转**

```python
from ui.chat.tts_pipeline import TTSPipelineController, TTSSegmentStatus


def test_pipeline_marks_segment_cancelled_when_new_turn_begins():
    pipeline = TTSPipelineController(max_translation_workers=1, max_tts_workers=1, queue_limit=8, segment_total_timeout_seconds=10)
    pipeline.begin_turn(utterance_id=1)
    pipeline.enqueue_text_segment(utterance_id=1, segment_id=0, text="你好。", needs_translation=False)

    pipeline.begin_turn(utterance_id=2)

    assert pipeline.segments[(1, 0)].status == TTSSegmentStatus.CANCELLED
```

- [ ] **Step 2: 运行测试，确认当前失败**

运行：

`python -m pytest tests/test_tts_pipeline.py -k cancelled_when_new_turn_begins -v`

预期：

- 失败，因为 `ui.chat.tts_pipeline` 尚不存在。

- [ ] **Step 3: 再写失败测试，锁定总超时会把句段推进到 timed_out**

```python
def test_pipeline_marks_segment_timed_out_after_total_timeout():
    pipeline = TTSPipelineController(max_translation_workers=1, max_tts_workers=1, queue_limit=8, segment_total_timeout_seconds=1)
    pipeline.begin_turn(utterance_id=1)
    pipeline.enqueue_text_segment(utterance_id=1, segment_id=0, text="你好。", needs_translation=False)
    pipeline.mark_synthesizing((1, 0), started_at=0.0)

    pipeline.collect_timed_out_segments(now=5.0)

    assert pipeline.segments[(1, 0)].status == TTSSegmentStatus.TIMED_OUT
```

- [ ] **Step 4: 运行测试，确认当前失败**

运行：

`python -m pytest tests/test_tts_pipeline.py -k timed_out_after_total_timeout -v`

预期：

- 失败，因为总超时模型还不存在。

- [ ] **Step 5: 写最小状态模型实现**

```python
# ui/chat/tts_pipeline.py
from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class TTSSegmentStatus(StrEnum):
    QUEUED = "queued"
    TRANSLATING = "translating"
    READY_FOR_TTS = "ready_for_tts"
    SYNTHESIZING = "synthesizing"
    STREAMING = "streaming"
    PLAYED = "played"
    FAILED = "failed"
    TIMED_OUT = "timed_out"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"


@dataclass
class TTSSegmentState:
    utterance_id: int
    segment_id: int
    text: str
    status: TTSSegmentStatus
    started_at: float | None = None


class TTSPipelineController:
    def __init__(self, max_translation_workers: int, max_tts_workers: int, queue_limit: int, segment_total_timeout_seconds: int):
        self._queue_limit = queue_limit
        self._segment_total_timeout_seconds = segment_total_timeout_seconds
        self.segments: dict[tuple[int, int], TTSSegmentState] = {}

    def begin_turn(self, utterance_id: int) -> None:
        for key, segment in list(self.segments.items()):
            if segment.utterance_id != utterance_id and segment.status not in {TTSSegmentStatus.PLAYED, TTSSegmentStatus.FAILED, TTSSegmentStatus.TIMED_OUT}:
                segment.status = TTSSegmentStatus.CANCELLED

    def enqueue_text_segment(self, utterance_id: int, segment_id: int, text: str, needs_translation: bool) -> None:
        status = TTSSegmentStatus.TRANSLATING if needs_translation else TTSSegmentStatus.READY_FOR_TTS
        self.segments[(utterance_id, segment_id)] = TTSSegmentState(utterance_id, segment_id, text, status)

    def mark_synthesizing(self, key: tuple[int, int], started_at: float) -> None:
        self.segments[key].status = TTSSegmentStatus.SYNTHESIZING
        self.segments[key].started_at = started_at

    def collect_timed_out_segments(self, now: float) -> list[tuple[int, int]]:
        timed_out = []
        for key, segment in self.segments.items():
            if segment.started_at is None:
                continue
            if now - segment.started_at > self._segment_total_timeout_seconds:
                segment.status = TTSSegmentStatus.TIMED_OUT
                timed_out.append(key)
        return timed_out
```

- [ ] **Step 6: 运行定向测试，确认通过**

运行：

`python -m pytest tests/test_tts_pipeline.py -q`

预期：

- 通过。

- [ ] **Step 7: 把 `ChatWindow` 的零散状态表逐步切到 pipeline**

```python
# ui/chat/window.py（概念性接线）
self._tts_pipeline = TTSPipelineController(
    max_translation_workers=runtime_config.max_translation_workers,
    max_tts_workers=runtime_config.max_tts_workers,
    queue_limit=runtime_config.tts_queue_limit,
    segment_total_timeout_seconds=runtime_config.segment_total_timeout_seconds,
)

def _begin_new_tts_turn(self) -> None:
    self._current_utterance_id += 1
    self._tts_pipeline.begin_turn(self._current_utterance_id)
    ...
```

- [ ] **Step 8: 运行 `ChatWindow` 聚焦测试，确认现有行为没被破坏**

运行：

`python -m pytest tests/test_chat_tts_flow.py -k "new_user_turn_invalidates_old_tts_results or new_user_turn_invalidates_old_translation_results" -v`

预期：

- 通过。

- [ ] **Step 9: 提交这一小步**

```bash
git add ui/chat/tts_pipeline.py ui/chat/window.py tests/test_tts_pipeline.py tests/test_chat_tts_flow.py
git commit -m "refactor(tts): add explicit segment lifecycle controller"
```

---

## 任务 4：把 GPT-SoVITS 与 ChatWindow 收口到有界流水线语义

**Files:**
- Modify: `tts/adapters/gptsovits.py`
- Modify: `ui/chat/window.py`
- Modify: `tests/test_tts_adapter.py`
- Modify: `tests/test_chat_tts_flow.py`

- [ ] **Step 1: 先写失败测试，锁定队列上限超出时要丢弃或跳过新增句段**

```python
def test_tts_enqueue_marks_segment_skipped_when_queue_limit_is_exceeded(chat_window, monkeypatch):
    chat_window._tts_pipeline._queue_limit = 1
    monkeypatch.setattr(
        chat_window,
        "_enqueue_tts_segment",
        ChatWindow._enqueue_tts_segment.__get__(chat_window, ChatWindow),
    )

    chat_window._enqueue_tts_segment("第一句。")
    chat_window._enqueue_tts_segment("第二句。")

    key = (chat_window._current_utterance_id, 1)
    assert chat_window._tts_pipeline.segments[key].status == "skipped"
```

- [ ] **Step 2: 运行测试，确认当前失败**

运行：

`python -m pytest tests/test_chat_tts_flow.py -k queue_limit_is_exceeded -v`

预期：

- 失败，因为当前实现虽然有 worker 上限，但还没有总队列上限语义。

- [ ] **Step 3: 再写失败测试，锁定适配器总超时后会发出 error/timed_out 语义**

```python
def test_pcm_stream_total_timeout_yields_error_event(monkeypatch):
    class _FakeResponse:
        status_code = 200
        headers = {
            "X-Audio-Sample-Rate": "32000",
            "X-Audio-Channels": "1",
            "X-Audio-Sample-Width": "2",
        }

        def iter_content(self, chunk_size=None):
            yield b"\x00\x01"
            raise TimeoutError("segment total timeout")

    class _FakeSession:
        def post(self, *args, **kwargs):
            return _FakeResponse()

    monkeypatch.setattr("tts.adapters.gptsovits.requests.Session", lambda: _FakeSession())
    adapter = GPTSoVITSAdapter(TTSConfig(engine="gptsovits", api_url="http://fake:9880", audio_mode="pcm_stream"))

    events = list(adapter.stream_synthesize("hello"))

    assert events[-1].kind == "error"
```

- [ ] **Step 4: 运行测试，确认当前失败**

运行：

`python -m pytest tests/test_tts_adapter.py -k total_timeout_yields_error_event -v`

预期：

- 失败，因为当前总超时语义还没真正进入适配器 / pipeline 协作路径。

- [ ] **Step 5: 写最小实现，把现有基础能力推进到 spec 语义**

```python
# ui/chat/window.py（概念性规则）
def _enqueue_tts_segment(self, text: str) -> None:
    decision = self._tts_pipeline.enqueue_or_skip(...)
    if decision == "skipped":
        return
    ...

def _poll_tts_timeouts(self) -> None:
    for key in self._tts_pipeline.collect_timed_out_segments(time.monotonic()):
        self._fail_segment(key, "segment total timeout")
```

```python
# tts/adapters/gptsovits.py（概念性规则）
def _yield_pcm_response(self, resp) -> Iterator[TTSStreamEvent]:
    ...
    except Exception as exc:
        yield TTSStreamEvent(kind="error", message=str(exc))
        return None
```

说明：

- 不需要把 `gptsovits.py` 变成复杂状态机；
- “总超时”应由 `ChatWindow` / `TTSPipelineController` 统一裁定，适配器只需要保证失败时稳定产出 `error` 事件；
- WAV 回退仍然保持在 `auto` 模式与“首个音频未真正起播”的现有边界内。

- [ ] **Step 6: 运行 TTS 聚焦回归**

运行：

`python -m pytest tests/test_tts_adapter.py -q`

`python -m pytest tests/test_chat_tts_flow.py -q`

预期：

- 通过。

- [ ] **Step 7: 提交这一小步**

```bash
git add tts/adapters/gptsovits.py ui/chat/window.py tests/test_tts_adapter.py tests/test_chat_tts_flow.py
git commit -m "feat(tts): close bounded pipeline timeout and queue semantics"
```

---

## 任务 5：Phase 4 后半段回归验证与文档同步

**Files:**
- Modify: `docs/README.md`
- Modify: `docs/architecture.md`
- Modify: `docs/development.md`
- Test: `tests/test_config_agent.py`
- Test: `tests/test_event_bus.py`
- Test: `tests/test_agent_page_events.py`
- Test: `tests/test_agent_log_events.py`
- Test: `tests/test_tts_pipeline.py`
- Test: `tests/test_tts_adapter.py`
- Test: `tests/test_chat_tts_flow.py`

- [ ] **Step 1: 运行后半段聚焦回归**

运行：

```bash
python -m pytest tests/test_config_agent.py -q
python -m pytest tests/test_event_bus.py tests/test_agent_page_events.py tests/test_agent_log_events.py -q
python -m pytest tests/test_tts_pipeline.py tests/test_tts_adapter.py tests/test_chat_tts_flow.py -q
```

预期：

- 全部通过。

- [ ] **Step 2: 用 `py_compile` 做语法 sanity check**

运行：

```bash
python -m py_compile core/event_bus.py core/ui_event_bridge.py ui/settings/pages/agent_page.py ui/chat/tts_pipeline.py ui/chat/window.py tts/adapters/gptsovits.py
```

预期：

- 无输出，退出码 0。

- [ ] **Step 3: 同步文档到真实实现状态**

```markdown
- `docs/README.md`
  增加 Phase 4 后半段收口 plan 入口。
- `docs/architecture.md`
  把 `UIEventBridge`、Agent 日志页主线程桥、`TTSPipelineController` 和句段生命周期写进架构说明。
- `docs/development.md`
  写明 `event_bus_runtime` 配置项、TTS 队列 / 总超时语义，以及新增测试入口。
```

- [ ] **Step 4: 运行最终聚焦回归，确认文档同步没有带来额外代码修改遗漏**

运行：

`python -m pytest tests/test_event_bus.py tests/test_tts_pipeline.py tests/test_tts_adapter.py tests/test_chat_tts_flow.py -q`

预期：

- 通过。

- [ ] **Step 5: 提交这一小步**

```bash
git add docs/README.md docs/architecture.md docs/development.md tests/test_config_agent.py tests/test_event_bus.py tests/test_agent_page_events.py tests/test_agent_log_events.py tests/test_tts_pipeline.py tests/test_tts_adapter.py tests/test_chat_tts_flow.py
git commit -m "docs: sync phase 4 back-half closure"
```

## 自检

- spec 覆盖检查：
  - EventBus 主线程桥与日志节流 → 任务 1-2
  - TTS 句段状态模型、取消语义、总超时、队列上限 → 任务 3-4
  - 文档同步与后半段验收 → 任务 5
- 当前已完成能力声明检查：
  - 不得把已经落地的“线程安全快照发布”“有限 PCM 读超时”“基础 worker 上限”再次当作待实现目标
  - 新任务必须只覆盖“未完成 + 已部分完成但未收口”的缺口
- 占位词检查：
  - 全文不应出现 `TODO`、`TBD`
  - 所有步骤都必须包含文件、测试命令和最小代码示例
- 命名一致性检查：
  - `UIEventBridge`、`EventBusRuntimeConfig`、`TTSPipelineController`、`TTSSegmentStatus` 在全文中保持一致
