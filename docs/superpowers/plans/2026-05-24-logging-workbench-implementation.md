# 日志工作台 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 Yumetsuki 增加独立的对话日志 / 系统日志工作台，提供结构化日志、默认持久化、时间戳、脱敏、导出与详情复制能力，并把现有 Agent 运行日志从配置页中抽离。

**Architecture:** 以统一 `log_service` 为核心，定义结构化 `LogEvent`、脱敏器和 JSONL 持久化写入器；运行期由 LLM / Agent / Tool / TTS 关键链路主动产生日志事件；设置中心新增 `对话日志` 与 `系统日志` 两个独立页面消费同一日志源的不同视图。现有 `AgentPage` 去除日志职责，只保留 Agent 配置。

**Tech Stack:** Python、PySide6、pytest、JSONL、现有 `ConfigManager` / `SettingsWindow` / `UIEventBridge` / `ChatWindow` / `LLMManager` / `AgentManager` / `ToolRegistry` / `GPTSoVITSAdapter`。

---

## 文件结构

### 新增文件

- `core/log_types.py`
  - 定义 `LogEvent`、日志 channel / level 常量、导出所需的序列化辅助函数。
- `core/log_sanitizer.py`
  - 负责脱敏规则：`api_key`、`token`、`authorization`、`cookie` 等字段。
- `core/log_service.py`
  - 日志入口、内存缓冲、JSONL 落盘、UI 订阅、导出、按日期切换文件。
- `ui/settings/pages/conversation_log_page.py`
  - 对话日志时间线页面。
- `ui/settings/pages/system_log_page.py`
  - 系统日志工作台页面。
- `tests/test_log_sanitizer.py`
  - 脱敏规则测试。
- `tests/test_log_service.py`
  - 结构化事件、JSONL 持久化、日期切换、导出测试。
- `tests/test_conversation_log_page.py`
  - 对话日志页渲染、过滤、复制测试。
- `tests/test_system_log_page.py`
  - 系统日志页筛选、批量刷新、导出、打开目录测试。
- `tests/test_logging_integration.py`
  - LLM / Agent / Tool / TTS 关键事件接线测试。

### 需要修改的现有文件

- `config/schema.py`
  - 为系统级日志运行时参数增加配置模型。
- `config/manager.py`
  - 继续沿用 `system_config.yaml`，仅通过 schema 扩展承载日志配置。
- `ui/settings/window.py`
  - 新增导航项、装配两个新页面，并调整 `Agent` 页面顺序。
- `ui/settings/pages/agent_page.py`
  - 移除“运行日志”Tab，仅保留 Agent 配置。
- `ui/chat/window.py`
  - 记录文本切分、句段入队、跳过、播放、取消等系统日志。
- `tts/adapters/gptsovits.py`
  - 记录 TTS 请求、响应摘要、错误与回退日志。
- `llm/manager.py`
  - 记录流式开始 / 完成、thinking、tool call 边界。
- `agent/manager.py`
  - 写入对话日志友好的用户输入 / 角色回复 / 工具摘要事件。
- `core/tool_registry.py`
  - 记录工具调用开始、参数摘要、结果摘要、错误与耗时。
- `docs/README.md`
- `docs/architecture.md`
- `docs/development.md`
- `CLAUDE.md`

---

## 任务 1：建立结构化日志模型、脱敏器与持久化服务

**Files:**
- Create: `core/log_types.py`
- Create: `core/log_sanitizer.py`
- Create: `core/log_service.py`
- Modify: `config/schema.py`
- Modify: `tests/test_config.py`
- Create: `tests/test_log_sanitizer.py`
- Create: `tests/test_log_service.py`

- [ ] **Step 1: 先写失败测试，锁定日志配置进入 `SystemConfig`**

```python
from config.schema import SystemConfig


def test_system_config_exposes_logging_runtime():
    cfg = SystemConfig()

    assert hasattr(cfg, "logging")
    assert cfg.logging.enabled is True
    assert cfg.logging.log_root == "data/logs"
    assert cfg.logging.system_flush_interval_ms == 200
```

- [ ] **Step 2: 运行测试，确认当前失败**

运行：

`python -m pytest tests/test_config.py -k logging_runtime -v`

预期：

- 失败，因为 `SystemConfig` 尚无 `logging` 配置。

- [ ] **Step 3: 再写失败测试，锁定脱敏行为**

```python
from core.log_sanitizer import sanitize_details


def test_sanitize_details_masks_sensitive_fields():
    payload = {
        "api_key": "sk-live-secret",
        "headers": {
            "Authorization": "Bearer top-secret",
            "Cookie": "session=abc",
        },
        "text": "hello",
    }

    sanitized = sanitize_details(payload)

    assert sanitized["api_key"] == "***"
    assert sanitized["headers"]["Authorization"] == "***"
    assert sanitized["headers"]["Cookie"] == "***"
    assert sanitized["text"] == "hello"
```

- [ ] **Step 4: 运行测试，确认当前失败**

运行：

`python -m pytest tests/test_log_sanitizer.py -v`

预期：

- 失败，因为 `core.log_sanitizer` 尚不存在。

- [ ] **Step 5: 再写失败测试，锁定系统日志按日期写 JSONL**

```python
from datetime import datetime

from core.log_service import LogService
from core.log_types import LogChannel, LogEvent, LogLevel


def test_log_service_writes_system_events_to_daily_jsonl(tmp_path):
    service = LogService(log_root=tmp_path, system_flush_interval_ms=0)
    event = LogEvent(
        id="evt-1",
        timestamp=datetime(2026, 5, 24, 21, 14, 3, 182000),
        channel=LogChannel.SYSTEM,
        level=LogLevel.INFO,
        source="chat.tts",
        event_type="tts.segment_enqueued",
        session_id="s1",
        utterance_id=1,
        summary="segment enqueued",
        details={"text": "你好。"},
        sensitive=False,
    )

    service.record(event)
    service.flush()

    log_file = tmp_path / "system" / "2026-05-24.jsonl"
    assert log_file.exists()
    assert '"event_type": "tts.segment_enqueued"' in log_file.read_text(encoding="utf-8")
```

- [ ] **Step 6: 运行测试，确认当前失败**

运行：

`python -m pytest tests/test_log_service.py -k writes_system_events_to_daily_jsonl -v`

预期：

- 失败，因为 `LogService` 和 `LogEvent` 尚不存在。

- [ ] **Step 7: 写最小实现，建立日志配置、类型、脱敏器与 JSONL 写入器**

```python
# config/schema.py
class LoggingConfig(BaseModel):
    enabled: bool = True
    log_root: str = "data/logs"
    system_flush_interval_ms: int = 200
    ui_buffer_limit: int = 500


class SystemConfig(BaseModel):
    ...
    logging: LoggingConfig = LoggingConfig()
```

```python
# core/log_types.py
from dataclasses import asdict, dataclass
from datetime import datetime
from enum import Enum


class LogChannel(str, Enum):
    CONVERSATION = "conversation"
    SYSTEM = "system"


class LogLevel(str, Enum):
    DEBUG = "debug"
    INFO = "info"
    WARN = "warn"
    ERROR = "error"


@dataclass(frozen=True)
class LogEvent:
    id: str
    timestamp: datetime
    channel: LogChannel
    level: LogLevel
    source: str
    event_type: str
    session_id: str
    utterance_id: int | None
    summary: str
    details: dict
    sensitive: bool = False

    def to_json_dict(self) -> dict:
        data = asdict(self)
        data["timestamp"] = self.timestamp.isoformat(timespec="milliseconds")
        data["channel"] = self.channel.value
        data["level"] = self.level.value
        return data
```

```python
# core/log_sanitizer.py
SENSITIVE_KEYS = {"api_key", "token", "password", "authorization", "cookie"}


def sanitize_details(value):
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            if key.lower() in SENSITIVE_KEYS:
                result[key] = "***"
            else:
                result[key] = sanitize_details(item)
        return result
    if isinstance(value, list):
        return [sanitize_details(item) for item in value]
    return value
```

```python
# core/log_service.py
import json
from pathlib import Path

from core.log_sanitizer import sanitize_details
from core.log_types import LogChannel, LogEvent


class LogService:
    def __init__(self, log_root: Path | str, system_flush_interval_ms: int = 200):
        self._root = Path(log_root)
        self._pending: list[LogEvent] = []

    def record(self, event: LogEvent) -> None:
        sanitized = LogEvent(
            **{**event.__dict__, "details": sanitize_details(event.details)}
        )
        self._pending.append(sanitized)

    def flush(self) -> None:
        while self._pending:
            event = self._pending.pop(0)
            folder = "system" if event.channel == LogChannel.SYSTEM else "conversation"
            filename = (
                f"{event.timestamp:%Y-%m-%d}.jsonl"
                if event.channel == LogChannel.SYSTEM
                else f"{event.session_id}.jsonl"
            )
            path = self._root / folder / filename
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(event.to_json_dict(), ensure_ascii=False) + "\n")
```

- [ ] **Step 8: 运行定向测试，确认通过**

运行：

`python -m pytest tests/test_config.py -k logging_runtime -v`

`python -m pytest tests/test_log_sanitizer.py -q`

`python -m pytest tests/test_log_service.py -k writes_system_events_to_daily_jsonl -v`

预期：

- 通过。

- [ ] **Step 9: 提交这一小步**

```bash
git add config/schema.py core/log_types.py core/log_sanitizer.py core/log_service.py tests/test_config.py tests/test_log_sanitizer.py tests/test_log_service.py
git commit -m "feat: add structured logging service foundation"
```

---

## 任务 2：接入运行期日志生产者，补齐 TTS / LLM / Tool / Agent 事件

**Files:**
- Modify: `ui/chat/window.py`
- Modify: `tts/adapters/gptsovits.py`
- Modify: `llm/manager.py`
- Modify: `agent/manager.py`
- Modify: `core/tool_registry.py`
- Create: `tests/test_logging_integration.py`

- [ ] **Step 1: 先写失败测试，锁定 TTS 句段入队会写系统日志**

```python
from datetime import datetime

from core.log_types import LogChannel
from ui.chat.window import ChatWindow


def test_enqueue_tts_segment_records_system_log(chat_window, monkeypatch):
    recorded = []
    monkeypatch.setattr(
        chat_window,
        "_record_log_event",
        lambda **kwargs: recorded.append(kwargs),
        raising=False,
    )
    monkeypatch.setattr(
        chat_window,
        "_enqueue_tts_segment",
        ChatWindow._enqueue_tts_segment.__get__(chat_window, ChatWindow),
    )

    chat_window._enqueue_tts_segment("你好。")

    assert recorded[0]["channel"] == LogChannel.SYSTEM
    assert recorded[0]["event_type"] == "tts.segment_enqueued"
```

- [ ] **Step 2: 运行测试，确认当前失败**

运行：

`python -m pytest tests/test_logging_integration.py -k segment_enqueued -v`

预期：

- 失败，因为聊天窗还没有统一日志入口。

- [ ] **Step 3: 再写失败测试，锁定 LLM / Tool / Agent 会产生日志摘要**

```python
from core.log_types import LogChannel


def test_agent_manager_records_conversation_log_for_user_and_reply(fake_agent_manager, monkeypatch):
    recorded = []
    monkeypatch.setattr(fake_agent_manager, "_record_log_event", lambda **kwargs: recorded.append(kwargs), raising=False)

    list(fake_agent_manager.chat_stream("测试输入"))

    event_types = [item["event_type"] for item in recorded if item["channel"] == LogChannel.CONVERSATION]
    assert "conversation.user_input" in event_types
    assert "conversation.assistant_reply" in event_types
```

- [ ] **Step 4: 运行测试，确认当前失败**

运行：

`python -m pytest tests/test_logging_integration.py -k conversation_log_for_user_and_reply -v`

预期：

- 失败，因为 `AgentManager` 还没有接入日志服务。

- [ ] **Step 5: 写最小实现，给关键链路补统一 `_record_log_event()` 接线**

```python
# llm/manager.py（概念性结构）
class LLMManager:
    def __init__(..., log_service=None):
        ...
        self._log_service = log_service

    def _record_log_event(self, **kwargs):
        if self._log_service is None:
            return
        self._log_service.record(build_log_event(**kwargs))
```

```python
# ui/chat/window.py（概念性结构）
self._record_log_event(
    channel=LogChannel.SYSTEM,
    level=LogLevel.INFO,
    source="chat.tts",
    event_type="tts.segment_enqueued",
    session_id=self._tts_session_id,
    utterance_id=self._current_utterance_id,
    summary=f"segment {segment_id} enqueued",
    details={"text": text, "needs_translation": needs_translation},
)
```

```python
# core/tool_registry.py（概念性结构）
started_at = time.perf_counter()
try:
    result = ...
    self._record_log_event(
        channel=LogChannel.SYSTEM,
        level=LogLevel.INFO,
        source="tool.registry",
        event_type="tool.call_completed",
        session_id=session_id,
        utterance_id=utterance_id,
        summary=f"{qualified_name} completed",
        details={"arguments": arguments, "elapsed_ms": elapsed_ms, "result_preview": str(result)[:200]},
    )
    return result
except Exception as exc:
    ...
```

- [ ] **Step 6: 运行接线测试，确认通过**

运行：

`python -m pytest tests/test_logging_integration.py -q`

预期：

- 通过。

- [ ] **Step 7: 提交这一小步**

```bash
git add ui/chat/window.py tts/adapters/gptsovits.py llm/manager.py agent/manager.py core/tool_registry.py tests/test_logging_integration.py
git commit -m "feat: emit structured runtime log events"
```

---

## 任务 3：新增对话日志 / 系统日志页面，并从 Agent 页面抽离运行日志

**Files:**
- Create: `ui/settings/pages/conversation_log_page.py`
- Create: `ui/settings/pages/system_log_page.py`
- Modify: `ui/settings/window.py`
- Modify: `ui/settings/pages/agent_page.py`
- Create: `tests/test_conversation_log_page.py`
- Create: `tests/test_system_log_page.py`
- Modify: `tests/test_settings_window.py`

- [ ] **Step 1: 先写失败测试，锁定设置中心导航新增两个日志页**

```python
from PySide6.QtWidgets import QPushButton

from ui.settings.window import SettingsWindow


def test_settings_window_navigation_includes_conversation_and_system_logs():
    window = SettingsWindow()
    labels = [button.text() for button in window.findChildren(QPushButton) if button.isCheckable()]

    assert "📝  对话日志" in labels
    assert "🧪  系统日志" in labels
```

- [ ] **Step 2: 运行测试，确认当前失败**

运行：

`python -m pytest tests/test_settings_window.py -k navigation_includes_conversation_and_system_logs -v`

预期：

- 失败，因为导航中还没有对应页面。

- [ ] **Step 3: 再写失败测试，锁定 `AgentPage` 不再包含日志 Tab**

```python
from ui.settings.pages.agent_page import AgentPage


def test_agent_page_tabs_no_longer_include_runtime_log():
    page = AgentPage()
    labels = [page._tabs.tabText(i) for i in range(page._tabs.count())]

    assert "运行日志" not in labels
    assert labels == ["规划", "反思", "多步推理", "主动行为"]
```

- [ ] **Step 4: 运行测试，确认当前失败**

运行：

`python -m pytest tests/test_system_log_page.py -k no_longer_include_runtime_log -v`

预期：

- 失败，因为 `AgentPage` 目前仍带日志 Tab。

- [ ] **Step 5: 写最小页面实现与导航接线**

```python
# ui/settings/window.py（概念性结构）
pages_info = [
    ("🤖  API 设定", 0),
    ("👤  角色管理", 1),
    ("🧠  记忆", 2),
    ("📝  对话日志", 3),
    ("🧪  系统日志", 4),
    ("🤖  Agent", 5),
    ("🧩  插件", 6),
    ("⚙  系统", 7),
]
```

```python
# ui/settings/pages/conversation_log_page.py
class ConversationLogPage(QWidget):
    def __init__(self, log_service, parent=None):
        ...
        self._timeline = QTextEdit()
        self._timeline.setReadOnly(True)
```

```python
# ui/settings/pages/system_log_page.py
class SystemLogPage(QWidget):
    def __init__(self, log_service, parent=None):
        ...
        self._log_text = QTextEdit()
        self._log_text.setReadOnly(True)
```

- [ ] **Step 6: 运行页面与导航测试，确认通过**

运行：

`python -m pytest tests/test_settings_window.py -k navigation_includes_conversation_and_system_logs -v`

`python -m pytest tests/test_conversation_log_page.py tests/test_system_log_page.py -q`

预期：

- 通过。

- [ ] **Step 7: 提交这一小步**

```bash
git add ui/settings/window.py ui/settings/pages/agent_page.py ui/settings/pages/conversation_log_page.py ui/settings/pages/system_log_page.py tests/test_settings_window.py tests/test_conversation_log_page.py tests/test_system_log_page.py
git commit -m "feat(ui): add conversation and system log pages"
```

---

## 任务 4：补齐筛选、导出、复制详情、打开目录与 UI 持续刷新

**Files:**
- Modify: `core/log_service.py`
- Modify: `ui/settings/pages/conversation_log_page.py`
- Modify: `ui/settings/pages/system_log_page.py`
- Modify: `tests/test_log_service.py`
- Modify: `tests/test_conversation_log_page.py`
- Modify: `tests/test_system_log_page.py`

- [ ] **Step 1: 先写失败测试，锁定系统日志导出当前筛选结果**

```python
from core.log_service import LogService


def test_log_service_exports_filtered_events_to_jsonl(tmp_path):
    service = LogService(log_root=tmp_path, system_flush_interval_ms=0)
    service.record_system("chat.tts", "tts.segment_enqueued", "segment enqueued", {"segment_id": 1}, session_id="s1")
    service.record_system("tool.registry", "tool.call_completed", "tool completed", {"tool": "echo"}, session_id="s1")

    export_path = tmp_path / "export.jsonl"
    service.export_events(export_path, channel="system", source="chat.tts")

    text = export_path.read_text(encoding="utf-8")
    assert "tts.segment_enqueued" in text
    assert "tool.call_completed" not in text
```

- [ ] **Step 2: 运行测试，确认当前失败**

运行：

`python -m pytest tests/test_log_service.py -k exports_filtered_events_to_jsonl -v`

预期：

- 失败，因为导出接口尚不存在。

- [ ] **Step 3: 再写失败测试，锁定系统日志页支持复制完整 JSON**

```python
def test_system_log_page_can_copy_selected_event_json(system_log_page, monkeypatch):
    captured = {}
    monkeypatch.setattr(system_log_page, "_copy_text", lambda text: captured.setdefault("text", text), raising=False)

    system_log_page._set_selected_event({
        "event_type": "tts.segment_enqueued",
        "summary": "segment enqueued",
        "details": {"segment_id": 1},
    })
    system_log_page._copy_selected_event_json()

    assert '"tts.segment_enqueued"' in captured["text"]
```

- [ ] **Step 4: 运行测试，确认当前失败**

运行：

`python -m pytest tests/test_system_log_page.py -k copy_selected_event_json -v`

预期：

- 失败，因为页面还没有详情复制能力。

- [ ] **Step 5: 写最小实现，补导出、复制、打开目录与刷新接口**

```python
# core/log_service.py
def export_events(self, path: Path | str, channel=None, source=None, session_id=None) -> None:
    events = self.query_events(channel=channel, source=source, session_id=session_id)
    ...

def query_events(self, channel=None, source=None, session_id=None) -> list[dict]:
    ...
```

```python
# ui/settings/pages/system_log_page.py
def _copy_selected_event_json(self) -> None:
    if self._selected_event is None:
        return
    self._copy_text(json.dumps(self._selected_event, ensure_ascii=False, indent=2))
```

```python
# ui/settings/pages/conversation_log_page.py
def _refresh_view(self) -> None:
    events = self._log_service.query_events(channel="conversation", session_id=self._current_session_id)
    ...
```

- [ ] **Step 6: 运行增强功能测试，确认通过**

运行：

`python -m pytest tests/test_log_service.py tests/test_conversation_log_page.py tests/test_system_log_page.py -q`

预期：

- 通过。

- [ ] **Step 7: 提交这一小步**

```bash
git add core/log_service.py ui/settings/pages/conversation_log_page.py ui/settings/pages/system_log_page.py tests/test_log_service.py tests/test_conversation_log_page.py tests/test_system_log_page.py
git commit -m "feat(ui): add log filtering export and detail actions"
```

---

## 任务 5：同步文档并完成日志工作台首版回归

**Files:**
- Modify: `docs/README.md`
- Modify: `docs/architecture.md`
- Modify: `docs/development.md`
- Modify: `CLAUDE.md`
- Test: `tests/test_config.py`
- Test: `tests/test_log_sanitizer.py`
- Test: `tests/test_log_service.py`
- Test: `tests/test_logging_integration.py`
- Test: `tests/test_conversation_log_page.py`
- Test: `tests/test_system_log_page.py`
- Test: `tests/test_settings_window.py`

- [ ] **Step 1: 运行日志工作台聚焦回归**

运行：

```bash
python -m pytest tests/test_config.py -q
python -m pytest tests/test_log_sanitizer.py tests/test_log_service.py tests/test_logging_integration.py -q
python -m pytest tests/test_conversation_log_page.py tests/test_system_log_page.py tests/test_settings_window.py -q
```

预期：

- 全部通过。

- [ ] **Step 2: 用 `py_compile` 做语法 sanity check**

运行：

```bash
python -m py_compile core/log_types.py core/log_sanitizer.py core/log_service.py ui/settings/pages/conversation_log_page.py ui/settings/pages/system_log_page.py ui/settings/window.py ui/settings/pages/agent_page.py ui/chat/window.py tts/adapters/gptsovits.py llm/manager.py agent/manager.py core/tool_registry.py
```

预期：

- 无输出，退出码 0。

- [ ] **Step 3: 同步文档**

```markdown
- `docs/README.md`
  - 增加日志工作台设计 / 实施状态入口
  - 更新设置中心页面结构
- `docs/architecture.md`
  - 增加 `log_service`、日志页面、结构化日志链路说明
- `docs/development.md`
  - 增加日志目录、测试入口、脱敏与导出约定
- `CLAUDE.md`
  - 更新下一步主线为日志工作台落地完成
```

- [ ] **Step 4: 运行最终聚焦回归**

运行：

`python -m pytest tests/test_log_sanitizer.py tests/test_log_service.py tests/test_logging_integration.py tests/test_conversation_log_page.py tests/test_system_log_page.py -q`

预期：

- 通过。

- [ ] **Step 5: 提交这一小步**

```bash
git add CLAUDE.md docs/README.md docs/architecture.md docs/development.md tests/test_config.py tests/test_log_sanitizer.py tests/test_log_service.py tests/test_logging_integration.py tests/test_conversation_log_page.py tests/test_system_log_page.py tests/test_settings_window.py
git commit -m "docs: sync logging workbench implementation"
```

## 自检

- spec 覆盖检查：
  - 独立 `对话日志` / `系统日志` 导航页 → 任务 3
  - 结构化 `LogEvent` / `log_service` / 脱敏 / JSONL → 任务 1
  - TTS / LLM / Tool / Agent 接线 → 任务 2
  - 导出 / 日期切文件 / 复制详情 → 任务 4
  - 文档与首版回归 → 任务 5
- placeholder 检查：
  - 全文无 `TODO` / `TBD`
  - 每个任务都给出具体文件、测试与命令
- 范围控制检查：
  - 不引入数据库、远程上传、全文索引、复杂分析面板
  - 首版只覆盖日志工作台最需要的可观测性与回看能力
