# Logging Workbench Polish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 补齐日志覆盖面，修复系统日志滚动与自动刷新问题，并把系统/对话日志页打磨到可筛选、可复制、可理解的状态。

**Architecture:** 保留现有 `LogService -> SettingsWindow -> ConversationLogPage / SystemLogPage` 结构，不重做事件模型，只在 `LogService` 增加页面查询辅助能力，在页面层引入双视图与最近会话选择，在 `AgentManager`、`LLMManager`、`SessionContextManager`、`ChatWindow` 等链路补结构化日志事件。系统日志仍以结构化事件为真源，连续文本视图只做选择与复制的投影。

**Tech Stack:** Python, PySide6, pytest

**Status:** 已完成。实现已覆盖 LogService 查询辅助、系统日志双视图与滚动保持、对话日志最近会话入口、记忆 / LLM / 切句 / TTS 日志接线，并通过聚焦自动化回归。

---

## Planned File Touches

- Modify: `core/log_service.py`
  - 增加“最近会话”和“来源列表”查询辅助方法，避免页面自己扫描原始事件
- Modify: `agent/manager.py`
  - 记录长期记忆命中摘要与计数
- Modify: `llm/manager.py`
  - 记录 LLM 流式累计摘要
- Modify: `session/manager.py`
  - 记录短期上下文摘要与 mem0 升格摘要
- Modify: `ui/chat/window.py`
  - 记录本地切句、TTS 入队、翻译摘要
- Modify: `ui/settings/pages/system_log_page.py`
  - 引入双视图、两层来源筛选、滚动保持逻辑、详情稳定刷新
- Modify: `ui/settings/pages/conversation_log_page.py`
  - 引入最近会话下拉、当前会话/全部会话切换、情绪胶囊样式调整
- Modify: `ui/settings/window.py`
  - 适配对话日志页和系统日志页的新会话接口
- Modify: `tests/test_system_log_page.py`
  - 覆盖双视图、筛选联动、滚动行为
- Modify: `tests/test_conversation_log_page.py`
  - 覆盖最近会话、当前会话/全部会话和情绪样式
- Modify: `tests/test_logging_integration.py`
  - 覆盖新增日志接线
- Modify: `docs/README.md`
  - 登记新实施计划

### Task 1: Extend LogService Query Helpers

**Files:**
- Modify: `core/log_service.py`
- Test: `tests/test_log_service.py`

- [ ] **Step 1: Write the failing tests for recent sessions and source listing**

```python
from core.log_service import LogService
from core.log_types import LogChannel, LogLevel, build_log_event


def test_list_conversation_sessions_returns_latest_first(tmp_path):
    service = LogService(tmp_path)
    service.record(build_log_event(
        channel=LogChannel.CONVERSATION,
        level=LogLevel.INFO,
        source="agent.manager",
        event_type="conversation.user_input",
        session_id="session-1",
        summary="用户输入: 你好",
        details={"text": "你好"},
    ))
    service.record(build_log_event(
        channel=LogChannel.CONVERSATION,
        level=LogLevel.INFO,
        source="agent.manager",
        event_type="conversation.user_input",
        session_id="session-2",
        summary="用户输入: 下午好",
        details={"text": "下午好"},
    ))

    sessions = service.list_conversation_sessions(limit=10)

    assert sessions[0]["session_id"] == "session-2"
    assert sessions[0]["label"]
    assert sessions[1]["session_id"] == "session-1"


def test_list_sources_returns_sorted_unique_sources(tmp_path):
    service = LogService(tmp_path)
    service.record_system("chat.tts", "tts.segment_enqueued", "segment", {}, session_id="s1")
    service.record_system("llm.manager", "llm.stream_started", "stream", {}, session_id="s1")
    service.record_system("chat.tts", "tts.segment_played", "played", {}, session_id="s1")

    assert service.list_sources() == ["chat.tts", "llm.manager"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_log_service.py -q`
Expected: FAIL with missing `list_conversation_sessions` / `list_sources`

- [ ] **Step 3: Write the minimal implementation in `core/log_service.py`**

```python
class LogService:
    def list_sources(self, channel=None) -> list[str]:
        events = self.query_events(channel=channel)
        return sorted({str(event.get("source", "")) for event in events if event.get("source")})

    def list_conversation_sessions(self, limit: int = 20) -> list[dict]:
        grouped: dict[str, dict] = {}
        for event in self.query_events(channel=LogChannel.CONVERSATION):
            session_id = event.get("session_id")
            if not session_id:
                continue
            current = grouped.get(session_id)
            if current is None or event.get("timestamp", "") > current.get("last_timestamp", ""):
                text = (event.get("details") or {}).get("text") or event.get("summary", "")
                grouped[session_id] = {
                    "session_id": session_id,
                    "last_timestamp": event.get("timestamp", ""),
                    "preview": str(text)[:24],
                }
        sessions = sorted(grouped.values(), key=lambda item: item["last_timestamp"], reverse=True)
        for item in sessions:
            item["label"] = f'{item["last_timestamp"][11:16]}  {item["preview"]}'
        return sessions[:limit]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_log_service.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add core/log_service.py tests/test_log_service.py
git commit -m "feat: add log service query helpers"
```

### Task 2: Rebuild System Log Page Around Two Views and Stable Refresh

**Files:**
- Modify: `ui/settings/pages/system_log_page.py`
- Test: `tests/test_system_log_page.py`

- [ ] **Step 1: Write failing tests for group/source filters and continuous text rendering**

```python
def test_system_log_page_filters_sources_by_group():
    page = SystemLogPage(_ServiceWithSources())

    page._group_filter.setCurrentText("TTS")
    page._rebuild_source_options()

    options = [page._source_filter.itemText(i) for i in range(page._source_filter.count())]
    assert "chat.tts" in options
    assert "llm.manager" not in options


def test_system_log_page_renders_continuous_text_view():
    page = SystemLogPage(_ServiceWithTtsEvent())
    page._view_mode.setCurrentText("连续文本")
    page._refresh_view()

    text = page._event_text_view.toPlainText()
    assert "chat.tts" in text
    assert "segment enqueued" in text
```

- [ ] **Step 2: Add failing tests for refresh behavior**

```python
def test_system_log_page_refresh_keeps_detail_scroll_position(qtbot):
    page = SystemLogPage(_ServiceWithManyEvents())
    page._refresh_view()
    page._event_list.setCurrentRow(0)
    page._detail_text.show()
    bar = page._detail_text.verticalScrollBar()
    bar.setValue(bar.maximum())

    page._refresh_view()

    assert bar.value() == bar.maximum()


def test_system_log_page_only_autoscrolls_when_user_is_near_bottom():
    page = SystemLogPage(_AppendOnlyService())
    page._refresh_view()
    page._event_text_view.show()
    bar = page._event_text_view.verticalScrollBar()
    bar.setValue(0)

    page._refresh_view()

    assert bar.value() == 0
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `python -m pytest tests/test_system_log_page.py -q`
Expected: FAIL with missing `_group_filter`, `_view_mode`, `_event_text_view`, and refresh assertions

- [ ] **Step 4: Implement dual-view controls and grouped source mapping**

```python
SOURCE_GROUPS = {
    "全部": set(),
    "记忆": {"session.manager", "memory.mem0"},
    "LLM": {"llm.manager"},
    "切句": {"chat.segmenter"},
    "TTS": {"chat.tts", "tts.gptsovits"},
    "工具": {"tool.registry"},
    "UI": {"chat.window", "ui.event_bridge"},
    "Agent": {"agent.manager"},
}

self._group_filter = QComboBox()
self._group_filter.addItems(SOURCE_GROUPS.keys())
self._group_filter.currentIndexChanged.connect(self._on_group_changed)

self._source_filter = QComboBox()
self._source_filter.currentIndexChanged.connect(self._refresh_view)

self._view_mode = QComboBox()
self._view_mode.addItems(["结构化列表", "连续文本"])
self._view_mode.currentIndexChanged.connect(self._sync_view_mode)

self._event_text_view = QTextEdit()
self._event_text_view.setReadOnly(True)
self._event_text_view.hide()
```

- [ ] **Step 5: Implement refresh logic that preserves user position**

```python
def _capture_scroll_state(self, widget):
    bar = widget.verticalScrollBar()
    return {
        "value": bar.value(),
        "maximum": bar.maximum(),
        "near_bottom": bar.maximum() - bar.value() <= 8,
    }


def _restore_scroll_state(self, widget, state):
    bar = widget.verticalScrollBar()
    if state["near_bottom"]:
        bar.setValue(bar.maximum())
    else:
        bar.setValue(min(state["value"], bar.maximum()))


def _set_selected_event(self, event):
    if self._event_key(event) == self._event_key(self._selected_event):
        return
    self._selected_event = event
    if event is None:
        self._detail_text.clear()
        self._detail_text.hide()
        return
    self._detail_text.setPlainText(json.dumps(event, ensure_ascii=False, indent=2))
    self._detail_text.show()
```

- [ ] **Step 6: Implement shared rendering for list view and continuous text view**

```python
def _render_event_text_block(self, event: dict) -> str:
    timestamp = event.get("timestamp", "")[11:23]
    level = (event.get("level", "info") or "info").upper()
    source = event.get("source", "unknown")
    body = self._body_text(event)
    return f"{timestamp}  {level}  {source}\n{body}\n"


def _render_event_text_document(self, events: list[dict]) -> str:
    return "\n".join(self._render_event_text_block(event) for event in events)
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `python -m pytest tests/test_system_log_page.py -q`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add ui/settings/pages/system_log_page.py tests/test_system_log_page.py
git commit -m "feat: polish system log page interactions"
```

### Task 3: Rework Conversation Log Page Session Entry and Emotion Styling

**Files:**
- Modify: `ui/settings/pages/conversation_log_page.py`
- Modify: `ui/settings/window.py`
- Test: `tests/test_conversation_log_page.py`

- [ ] **Step 1: Write failing tests for recent sessions and current/all toggles**

```python
def test_conversation_log_page_loads_recent_session_options():
    page = ConversationLogPage(_ServiceWithSessions())

    labels = [page._session_selector.itemText(i) for i in range(page._session_selector.count())]
    assert any("10:25" in label for label in labels)


def test_conversation_log_page_can_switch_between_current_and_all_events():
    page = ConversationLogPage(_ServiceWithSessions())
    page.set_session_id("session-1")
    page._scope_filter.setCurrentText("全部会话")
    page._refresh_view()

    text = page._timeline.toPlainText()
    assert "session-1 文本" in text
    assert "session-2 文本" in text
```

- [ ] **Step 2: Add a failing test for the wider emotion chip markup**

```python
def test_conversation_log_page_renders_wider_emotion_chip():
    page = ConversationLogPage(_ServiceWithEmotionReply())
    page._refresh_view()

    html = page._timeline.toHtml()
    assert "padding: 4px 12px" in html
    assert "border-radius: 12px" in html
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `python -m pytest tests/test_conversation_log_page.py -q`
Expected: FAIL with missing `_session_selector` / `_scope_filter` and old emotion chip markup

- [ ] **Step 4: Replace free-text session input with recent session selector**

```python
self._scope_filter = QComboBox()
self._scope_filter.addItem("当前会话", "current")
self._scope_filter.addItem("全部会话", "all")
self._scope_filter.currentIndexChanged.connect(self._refresh_view)

self._session_selector = QComboBox()
self._session_selector.currentIndexChanged.connect(self._on_session_selected)

def _reload_sessions(self) -> None:
    sessions = self._log_service.list_conversation_sessions(limit=20)
    current = self._current_session_id
    self._session_selector.blockSignals(True)
    self._session_selector.clear()
    for item in sessions:
        self._session_selector.addItem(item["label"], item["session_id"])
    self._session_selector.blockSignals(False)
    if current:
        index = self._session_selector.findData(current)
        if index >= 0:
            self._session_selector.setCurrentIndex(index)
```

- [ ] **Step 5: Update `SettingsWindow` to seed both pages with the current chat session**

```python
if hasattr(self._conversation_log_page, "set_session_id"):
    self._conversation_log_page.set_session_id(self._chat_window._tts_session_id)
if hasattr(self._system_log_page, "set_session_id"):
    self._system_log_page.set_session_id(self._chat_window._tts_session_id)
```

- [ ] **Step 6: Update emotion chip rendering**

```python
inline_emotion = (
    ' <span style="display:inline-block; margin-left: 8px; padding: 4px 12px; '
    'background: rgba(255, 236, 242, 0.98); border: 1px solid rgba(212, 86, 122, 0.20); '
    'border-radius: 12px; font-size: 11px; color: #8b4d66; vertical-align: middle;">'
    f'{html_escape(str(emotion))}</span>'
)
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `python -m pytest tests/test_conversation_log_page.py -q`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add ui/settings/pages/conversation_log_page.py ui/settings/window.py tests/test_conversation_log_page.py
git commit -m "feat: improve conversation log navigation"
```

### Task 4: Add Memory and LLM Logging Coverage

**Files:**
- Modify: `agent/manager.py`
- Modify: `llm/manager.py`
- Modify: `session/manager.py`
- Test: `tests/test_logging_integration.py`

- [ ] **Step 1: Write failing integration tests for memory hits, prompt context, and stream progress**

```python
def test_agent_manager_records_memory_retrieval_summary(monkeypatch):
    llm = _FakeLLMManager("[emotion:开心]收到")
    memory_store = type("M", (), {"search_relevant": lambda self, *_args, **_kwargs: ["记忆1", "记忆2"]})()
    manager = AgentManager(
        llm_manager=llm,
        planner=FakePlanner(FakePlan(mode="chat", goal="reply")),
        executor=FakeExecutor(""),
        memory_store=memory_store,
        user_id="u1",
    )
    recorded = []
    monkeypatch.setattr(manager, "_record_log_event", lambda **kwargs: recorded.append(kwargs), raising=False)

    list(manager.chat_stream("测试输入"))

    assert any(item["event_type"] == "memory.retrieved" for item in recorded)


def test_llm_manager_records_stream_progress(monkeypatch):
    captured = []

    class _FakeAdapter:
        def stream_chat(self, messages, tools=None):
            yield "你"
            yield "好"

    manager = LLMManager(
        LLMConfig(),
        log_service=type("S", (), {"record": lambda self, event: captured.append(event)})(),
    )
    manager._adapter = _FakeAdapter()

    list(manager.chat_stream("测试输入"))

    assert any(event.event_type == "llm.stream_progress" for event in captured)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_logging_integration.py -q`
Expected: FAIL with missing `memory.retrieved`, `session.prompt_context_built`, or `llm.stream_progress`

- [ ] **Step 3: Implement memory retrieval and prompt context logs**

```python
def _search_memories(self, user_input: str) -> list[str]:
    if not self._memory_store:
        return []
    memories = self._memory_store.search_relevant(user_input, user_id=self._user_id)
    self._record_log_event(
        channel=LogChannel.SYSTEM,
        level=LogLevel.INFO,
        source="agent.manager",
        event_type="memory.retrieved",
        session_id=self._session_id,
        summary=f"memory hits: {len(memories)}",
        details={"count": len(memories), "preview": memories[:3]},
    )
    return memories
```

```python
def build_prompt_context(self, ctx: SessionContext) -> str:
    prompt = self._policy.build_prompt_context(ctx)
    if self._log_service is not None:
        self._log_service.record_system(
            "session.manager",
            "session.prompt_context_built",
            "session prompt context built",
            {
                "recent_turn_count": len(ctx.recent_turns),
                "working_fact_count": len(ctx.working_facts),
                "preview": prompt[:120],
            },
            session_id=ctx.session_id,
        )
    return prompt
```

- [ ] **Step 4: Implement LLM stream progress logging**

```python
if chunk.content:
    full_response += chunk.content
    self._record_log_event(
        channel=LogChannel.SYSTEM,
        level=LogLevel.INFO,
        source="llm.manager",
        event_type="llm.stream_progress",
        session_id=self._session_id,
        summary="LLM stream progress",
        details={"response_length": len(full_response), "tail_preview": full_response[-80:]},
    )
    yield self._processor.process(full_response)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_logging_integration.py -q`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add agent/manager.py llm/manager.py session/manager.py tests/test_logging_integration.py
git commit -m "feat: expand memory and llm logging"
```

### Task 5: Add Segmenter and TTS Pipeline Logging Coverage

**Files:**
- Modify: `ui/chat/window.py`
- Test: `tests/test_logging_integration.py`
- Test: `tests/test_chat_tts_flow.py`

- [ ] **Step 1: Write failing tests for local segmenting and translated enqueue logs**

```python
def test_chat_window_logs_segment_text_before_enqueue(monkeypatch):
    _app()
    monkeypatch.setattr("ui.chat.window.LLMManager", _FakeLLMManager)
    monkeypatch.setattr("ui.chat.window.AgentManager", _FakeAgentManager)
    monkeypatch.setattr("ui.chat.window.SpriteManager", _FakeSpriteManager)
    chat_window = ChatWindow(LLMConfig(), tts_config=TTSConfig(engine="gptsovits", api_url="http://fake:9880"))
    recorded = []
    monkeypatch.setattr(chat_window, "_record_log_event", lambda **kwargs: recorded.append(kwargs), raising=False)

    chat_window._enqueue_tts_segment("你好。")

    assert any(item["event_type"] == "tts.segment_enqueued" for item in recorded)
    assert any(item["event_type"] == "chat.segmenter.segment_ready" for item in recorded)


def test_chat_window_logs_translation_result(monkeypatch):
    _app()
    monkeypatch.setattr("ui.chat.window.LLMManager", _FakeLLMManager)
    monkeypatch.setattr("ui.chat.window.AgentManager", _FakeAgentManager)
    monkeypatch.setattr("ui.chat.window.SpriteManager", _FakeSpriteManager)
    chat_window = ChatWindow(
        LLMConfig(),
        tts_config=TTSConfig(engine="gptsovits", api_url="http://fake:9880"),
    )
    recorded = []
    monkeypatch.setattr(chat_window, "_record_log_event", lambda **kwargs: recorded.append(kwargs), raising=False)
    monkeypatch.setattr(chat_window, "_start_tts_worker", lambda *_args, **_kwargs: None, raising=False)

    chat_window._begin_new_tts_turn()
    chat_window._handle_translation_result(chat_window._current_utterance_id, 0, "hello")

    assert any(item["event_type"] == "tts.translation_completed" for item in recorded)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_logging_integration.py tests/test_chat_tts_flow.py -q`
Expected: FAIL with missing `chat.segmenter.segment_ready` / `tts.translation_completed`

- [ ] **Step 3: Implement local segmenter logging in `ui/chat/window.py`**

```python
for segment in self._extract_tts_segments():
    self._record_log_event(
        channel=LogChannel.SYSTEM,
        level=LogLevel.INFO,
        source="chat.segmenter",
        event_type="chat.segmenter.segment_ready",
        session_id=self._tts_session_id,
        utterance_id=self._current_utterance_id,
        summary=f"segment ready {self._next_segment_id}",
        details={"text": segment, "committed_length": len(self._tts_committed_text)},
    )
    self._tts_committed_text += segment
    self._enqueue_tts_segment(segment)
```

- [ ] **Step 4: Implement translation result logging**

```python
def _handle_translation_result(self, utterance_id: int, segment_id: int, translated_text: str | None) -> None:
    if utterance_id != self._current_utterance_id:
        return
    translated = (translated_text or "").strip()
    if not translated:
        self._complete_tts_segment(utterance_id, segment_id, None)
        return
    self._record_log_event(
        channel=LogChannel.SYSTEM,
        level=LogLevel.INFO,
        source="chat.tts",
        event_type="tts.translation_completed",
        session_id=self._tts_session_id,
        utterance_id=utterance_id,
        summary=f"segment {segment_id} translated",
        details={"segment_id": segment_id, "translated_text": translated[:120]},
    )
    self._tts_pipeline.mark_ready_for_tts((utterance_id, segment_id), text=translated)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_logging_integration.py tests/test_chat_tts_flow.py -q`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add ui/chat/window.py tests/test_logging_integration.py tests/test_chat_tts_flow.py
git commit -m "feat: add segmenter and tts trace logs"
```

### Task 6: Sync Documentation Index

**Files:**
- Modify: `docs/README.md`

- [ ] **Step 1: Add the new implementation plan to the documentation index**

```markdown
- [日志工作台打磨实施计划](./superpowers/plans/2026-05-24-logging-workbench-polish-implementation.md)
  日志覆盖面、滚动行为、复制体验与筛选模型的实施拆解
```

- [ ] **Step 2: Verify the plan link is present**

Run: `python -c "from pathlib import Path; text = Path('docs/README.md').read_text(encoding='utf-8'); print('2026-05-24-logging-workbench-polish-implementation.md' in text)"`
Expected: `True`

- [ ] **Step 3: Commit**

```bash
git add docs/README.md
git commit -m "docs: index logging workbench polish plan"
```

## Verification Checklist

- Run: `python -m pytest tests/test_log_service.py tests/test_system_log_page.py tests/test_conversation_log_page.py tests/test_logging_integration.py tests/test_chat_tts_flow.py -q`
- Run: `python -m py_compile core/log_service.py agent/manager.py llm/manager.py session/manager.py ui/settings/pages/system_log_page.py ui/settings/pages/conversation_log_page.py ui/chat/window.py ui/settings/window.py`
- Manually verify in the settings window:
  - 系统日志能在 `结构化列表` / `连续文本` 间切换
  - 连续文本视图支持鼠标拖选复制
  - 非底部时自动刷新不会强制跳到底部
  - 详情区滚轮滚动不会在自动刷新后回弹到顶部
  - 来源筛选能先按业务链路再按具体模块收窄
  - 对话日志默认展示“最近会话”而不是裸 `session_id`
  - 对话日志情绪标签比当前更宽、更圆
