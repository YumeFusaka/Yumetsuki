# Agent 日志对话显示 + 桌宠窗口缩放优化 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Agent 日志增加用户/角色对话和 thinking 显示（混合时间线）；桌宠 ChatWindow 支持长文本滚动、全元素等比缩放、对话框区域扩大到 50%。

**Architecture:** 扩展现有 EventBus 事件系统新增 3 个事件类型（USER_INPUT / ASSISTANT_REPLY / THINKING），在 AgentManager.chat_stream 中发布；ChatWindow 用 QScrollArea 包裹对话文本，_apply_scale() 中动态计算所有尺寸并重建 stylesheet。

**Tech Stack:** PySide6, Python 3.11+, 现有 EventBus

---

## 文件结构

| 文件 | 职责 |
|------|------|
| `agent/manager.py` | 新增 3 个事件常量 + 在 chat_stream 中发布 USER_INPUT / ASSISTANT_REPLY / THINKING |
| `ui/settings/pages/agent_page.py` | 订阅新事件、HTML 富文本格式化、thinking 折叠逻辑、时间戳 |
| `ui/chat/window.py` | QScrollArea 包裹 dialog_label、等比缩放、panel 比例 50% |
| `tests/test_agent_log_events.py` | 验证新事件发布 |
| `tests/test_chat_window_scale.py` | 验证缩放逻辑 |

---

### Task 1: 新增 Agent 事件类型

**Files:**
- Modify: `agent/manager.py:15-23`
- Test: `tests/test_agent_log_events.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_agent_log_events.py
from agent.manager import AgentEvents

def test_new_event_constants_exist():
    assert hasattr(AgentEvents, "USER_INPUT")
    assert hasattr(AgentEvents, "ASSISTANT_REPLY")
    assert hasattr(AgentEvents, "THINKING")
    assert AgentEvents.USER_INPUT == "agent.user_input"
    assert AgentEvents.ASSISTANT_REPLY == "agent.assistant_reply"
    assert AgentEvents.THINKING == "agent.thinking"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_agent_log_events.py::test_new_event_constants_exist -v`
Expected: FAIL — `AttributeError: type object 'AgentEvents' has no attribute 'USER_INPUT'`

- [ ] **Step 3: 添加事件常量**

在 `agent/manager.py` 的 `AgentEvents` 类中添加：

```python
class AgentEvents:
    PLANNER_DECIDED = "agent.planner_decided"
    MEMORY_RETRIEVED = "agent.memory_retrieved"
    TOOL_EXECUTED = "agent.tool_executed"
    TOOL_SKIPPED = "agent.tool_skipped"
    REFLECTION_COMPLETE = "agent.reflection_complete"
    LLM_STARTED = "agent.llm_started"
    LLM_COMPLETE = "agent.llm_complete"
    MULTI_STEP_PROGRESS = "agent.multi_step_progress"
    USER_INPUT = "agent.user_input"
    ASSISTANT_REPLY = "agent.assistant_reply"
    THINKING = "agent.thinking"
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_agent_log_events.py::test_new_event_constants_exist -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add agent/manager.py tests/test_agent_log_events.py
git commit -m "feat: 新增 Agent 对话事件类型 USER_INPUT/ASSISTANT_REPLY/THINKING"
```

---

### Task 2: 在 chat_stream 中发布新事件

**Files:**
- Modify: `agent/manager.py:59-108`
- Test: `tests/test_agent_log_events.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_agent_log_events.py (追加)
from unittest.mock import MagicMock, patch
from agent.manager import AgentManager, AgentEvents
from core.event_bus import EventBus


def test_chat_stream_publishes_user_input_and_reply():
    """chat_stream 应发布 USER_INPUT 和 ASSISTANT_REPLY 事件。"""
    bus = EventBus()
    received = []
    bus.subscribe(AgentEvents.USER_INPUT, lambda d: received.append(("user", d)))
    bus.subscribe(AgentEvents.ASSISTANT_REPLY, lambda d: received.append(("reply", d)))

    mock_llm = MagicMock()
    from llm.text_processor import ProcessedText
    mock_llm.chat_stream.return_value = iter([ProcessedText(clean_text="你好", emotion=None)])

    mgr = AgentManager(
        llm_manager=mock_llm,
        event_bus_instance=bus,
    )
    # 消费 generator
    list(mgr.chat_stream("测试输入"))

    user_events = [e for e in received if e[0] == "user"]
    reply_events = [e for e in received if e[0] == "reply"]
    assert len(user_events) == 1
    assert user_events[0][1]["text"] == "测试输入"
    assert len(reply_events) == 1
    assert reply_events[0][1]["text"] == "你好"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_agent_log_events.py::test_chat_stream_publishes_user_input_and_reply -v`
Expected: FAIL — 事件未被发布

- [ ] **Step 3: 在 chat_stream 中发布事件**

修改 `agent/manager.py` 的 `chat_stream` 方法：

```python
def chat_stream(self, user_input: str) -> Generator[ProcessedText, None, None]:
    # 发布用户输入事件
    self._event_bus.publish(AgentEvents.USER_INPUT, {"text": user_input})

    memories = self._search_memories(user_input)
    # ... 现有逻辑不变 ...

    self._event_bus.publish(AgentEvents.LLM_COMPLETE, {
        "response_length": len(assistant_response),
    })

    # 发布角色回复事件
    self._event_bus.publish(AgentEvents.ASSISTANT_REPLY, {
        "text": assistant_response,
        "character_name": "",  # 由 UI 层填充角色名
    })

    # ... 后续反思逻辑不变 ...
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_agent_log_events.py -v`
Expected: ALL PASS

- [ ] **Step 5: 提交**

```bash
git add agent/manager.py tests/test_agent_log_events.py
git commit -m "feat: chat_stream 发布 USER_INPUT 和 ASSISTANT_REPLY 事件"
```

---

### Task 3: Thinking 事件支持

**Files:**
- Modify: `llm/adapters/openai_compat.py:12-50`
- Modify: `llm/adapter.py` (LLMStreamChunk 增加 thinking 字段)
- Modify: `agent/manager.py` (转发 thinking)
- Test: `tests/test_agent_log_events.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_agent_log_events.py (追加)
from llm.adapter import LLMStreamChunk


def test_stream_chunk_has_thinking_field():
    chunk = LLMStreamChunk(thinking="我在思考...")
    assert chunk.thinking == "我在思考..."
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_agent_log_events.py::test_stream_chunk_has_thinking_field -v`
Expected: FAIL — `TypeError: unexpected keyword argument 'thinking'`

- [ ] **Step 3: 扩展 LLMStreamChunk**

在 `llm/adapter.py` 的 `LLMStreamChunk` dataclass 中添加：

```python
@dataclass
class LLMStreamChunk:
    content: str = ""
    tool_calls: list[ToolCall] | None = None
    thinking: str = ""
```

- [ ] **Step 4: 在 OpenAI 适配器中捕获 thinking**

修改 `llm/adapters/openai_compat.py` 的 `stream_chat` 方法，在 chunk 循环中检测 `reasoning_content`（OpenAI-compatible API 的 thinking 字段）：

```python
for chunk in response:
    if not chunk.choices:
        continue
    delta = chunk.choices[0].delta
    # 捕获 thinking/reasoning tokens
    reasoning = getattr(delta, "reasoning_content", None) or getattr(delta, "thinking", None)
    if reasoning:
        yield LLMStreamChunk(thinking=reasoning)
    if delta.content:
        yield delta.content
    # ... tool_calls 逻辑不变 ...
```

- [ ] **Step 5: 在 LLMManager 中转发 thinking 事件**

修改 `llm/manager.py` 的 `chat_stream`，当收到 thinking chunk 时通过 yield 传递：

```python
for chunk in self._adapter.stream_chat(messages, tools=tools):
    if isinstance(chunk, LLMStreamChunk):
        if chunk.thinking:
            yield ProcessedText(clean_text=full_response, emotion=None, thinking=chunk.thinking)
        if chunk.content:
            full_response += chunk.content
            yield self._processor.process(full_response)
        # ... 其余不变
```

同时在 `llm/text_processor.py` 的 `ProcessedText` 中添加 `thinking: str = ""` 字段。

- [ ] **Step 6: 在 AgentManager 中发布 THINKING 事件**

修改 `agent/manager.py` 的 `chat_stream`，在 yield result 前检查 thinking：

```python
for result in self._llm_manager.chat_stream(user_input, extra_context=extra_context):
    if result.thinking:
        self._event_bus.publish(AgentEvents.THINKING, {"text": result.thinking})
    final_result = result
    assistant_response = result.clean_text
    yield result
```

- [ ] **Step 7: 运行测试确认通过**

Run: `python -m pytest tests/test_agent_log_events.py -v`
Expected: ALL PASS

- [ ] **Step 8: 提交**

```bash
git add llm/adapter.py llm/adapters/openai_compat.py llm/manager.py llm/text_processor.py agent/manager.py tests/test_agent_log_events.py
git commit -m "feat: 支持 thinking tokens 捕获和事件发布"
```

---

### Task 4: Agent 日志 UI — 订阅新事件 + 富文本格式化

**Files:**
- Modify: `ui/settings/pages/agent_page.py:474-560`

- [ ] **Step 1: 订阅新事件**

在 `_setup_event_subscription` 方法末尾添加：

```python
event_bus.subscribe(AgentEvents.USER_INPUT, self._on_user_input)
event_bus.subscribe(AgentEvents.ASSISTANT_REPLY, self._on_assistant_reply)
event_bus.subscribe(AgentEvents.THINKING, self._on_thinking)
```

- [ ] **Step 2: 实现事件处理方法**

```python
def _on_user_input(self, data):
    text = data.get("text", "")
    self._log_handler.log_entry.emit(
        f'<span style="color:#888;font-size:11px;">[{self._timestamp()}]</span> '
        f'<span style="color:#5f6fb2;font-weight:bold;">[User]</span> {self._escape(text)}'
    )

def _on_assistant_reply(self, data):
    text = data.get("text", "")
    name = data.get("character_name", "") or "Assistant"
    self._log_handler.log_entry.emit(
        f'<span style="color:#888;font-size:11px;">[{self._timestamp()}]</span> '
        f'<span style="color:#9b3060;font-weight:bold;">[{self._escape(name)}]</span> {self._escape(text)}'
    )

def _on_thinking(self, data):
    text = data.get("text", "")
    preview = text[:80]
    suffix = "…" if len(text) > 80 else ""
    self._log_handler.log_entry.emit(
        f'<span style="color:#888;font-size:11px;">[{self._timestamp()}]</span> '
        f'<span style="color:#888;font-style:italic;">[Thinking]</span> '
        f'<span style="color:#888;font-style:italic;">{self._escape(preview)}{suffix}</span>'
    )
```

- [ ] **Step 3: 添加辅助方法**

```python
from datetime import datetime
from html import escape as html_escape

def _timestamp(self) -> str:
    return datetime.now().strftime("%H:%M:%S")

def _escape(self, text: str) -> str:
    return html_escape(text).replace("\n", "<br>")
```

- [ ] **Step 4: 修改 _append_log 支持 HTML**

将 `self._log_text.append(text)` 改为 `self._log_text.insertHtml(text + "<br>")` 以支持富文本。

同时给现有的系统事件处理方法（`_on_planner_decided` 等）也加上时间戳和 HTML 格式：

```python
def _on_planner_decided(self, data):
    mode = data.get("mode", "unknown")
    tool = data.get("tool_name")
    multi = data.get("needs_multi_step", False)
    if multi:
        msg = "路由到多步推理模式"
    elif mode == "tool" and tool:
        msg = f"路由到工具: {tool}"
    else:
        msg = "路由到对话模式"
    self._log_handler.log_entry.emit(
        f'<span style="color:#888;font-size:11px;">[{self._timestamp()}]</span> '
        f'<span style="color:#6b8a7a;">[Planner]</span> {msg}'
    )
```

对其他 `_on_*` 方法做类似改造（保持原有信息，加时间戳和 HTML span）。

- [ ] **Step 5: 手动验证**

Run: `python main.py`
打开设置 → Agent → 运行日志 tab，发送一条消息，确认日志中出现带颜色的 [User] 和 [角色名] 条目。

- [ ] **Step 6: 提交**

```bash
git add ui/settings/pages/agent_page.py
git commit -m "feat: Agent 日志显示对话内容和 thinking（HTML 富文本 + 时间戳）"
```

---

### Task 5: ChatWindow — 对话框区域扩大到 50%

**Files:**
- Modify: `ui/chat/window.py:234-241`
- Test: `tests/test_chat_window_scale.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_chat_window_scale.py
import sys
from unittest.mock import MagicMock, patch

def test_panel_height_is_50_percent():
    """对话框 panel 应占窗口高度的 50%。"""
    # 读取源码验证比例常量
    import ui.chat.window as win_module
    import inspect
    source = inspect.getsource(win_module.ChatWindow._apply_scale)
    assert "0.50" in source or "0.5" in source, "panel 比例应为 50%"
    assert "0.38" not in source, "旧的 38% 比例应已移除"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_chat_window_scale.py::test_panel_height_is_50_percent -v`
Expected: FAIL — 源码中仍是 0.38

- [ ] **Step 3: 修改 panel 比例**

在 `ui/chat/window.py` 的 `_apply_scale` 方法中：

```python
def _apply_scale(self):
    w = int(self.BASE_WIDTH * self._scale)
    h = int(self.BASE_HEIGHT * self._scale)
    self.setFixedSize(w, h)
    panel_h = int(h * 0.50)
    self._panel.setGeometry(10, h - panel_h - 6, w - 20, panel_h)
    self._reload_sprite()
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_chat_window_scale.py::test_panel_height_is_50_percent -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add ui/chat/window.py tests/test_chat_window_scale.py
git commit -m "feat: 桌宠对话框区域从 38% 扩大到 50%"
```

---

### Task 6: ChatWindow — QScrollArea 包裹对话文本

**Files:**
- Modify: `ui/chat/window.py:48-66` (ConversationPane)
- Modify: `ui/chat/window.py:144-209` (_setup_ui)

- [ ] **Step 1: 修改 ConversationPane 添加 QScrollArea**

```python
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QLabel, QPushButton, QMenu,
    QApplication, QSizePolicy, QScrollArea,
)

class ConversationPane(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.name_label = QLabel("...", self)
        self.name_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)

        # dialog_label 包裹在 QScrollArea 中
        self._scroll_area = QScrollArea(self)
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._scroll_area.setFrameShape(QScrollArea.Shape.NoFrame)
        self._scroll_area.setStyleSheet("""
            QScrollArea { background: transparent; border: none; }
            QScrollBar:vertical {
                width: 6px; background: transparent;
            }
            QScrollBar::handle:vertical {
                background: rgba(212, 86, 122, 0.4); border-radius: 3px; min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background: rgba(212, 86, 122, 0.6);
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: transparent;
            }
        """)

        self.dialog_label = QLabel("...")
        self.dialog_label.setTextFormat(Qt.TextFormat.RichText)
        self.dialog_label.setWordWrap(True)
        self.dialog_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.dialog_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._scroll_area.setWidget(self.dialog_label)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        name_h = 24
        gap = 8
        self.name_label.setGeometry(0, 0, self.width(), name_h)
        self._scroll_area.setGeometry(0, name_h + gap, self.width(), max(0, self.height() - name_h - gap))

    def scroll_to_top(self):
        self._scroll_area.verticalScrollBar().setValue(0)
```

- [ ] **Step 2: 在 _set_dialog_text 中调用 scroll_to_top**

修改 `ChatWindow._set_dialog_text`：

```python
def _set_dialog_text(self, text: str) -> None:
    body = escape(text).replace("\n", "<br>")
    self._dialog_box.setText(
        f"<div style='line-height: 145%; color: #4a3040; font-size: 15px;'>{body}</div>"
    )
    self._conversation_pane.scroll_to_top()
```

- [ ] **Step 3: 手动验证**

Run: `python main.py`
发送一条很长的消息让角色回复长文本，确认对话框出现滚动条且可滚动。

- [ ] **Step 4: 提交**

```bash
git add ui/chat/window.py
git commit -m "feat: 桌宠对话框支持长文本滚动（QScrollArea）"
```

---

### Task 7: ChatWindow — 全元素等比缩放

**Files:**
- Modify: `ui/chat/window.py`
- Test: `tests/test_chat_window_scale.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_chat_window_scale.py (追加)
def test_scale_constants_defined():
    """缩放基准常量应存在。"""
    from ui.chat.window import ChatWindow
    assert hasattr(ChatWindow, "BASE_FONT")
    assert hasattr(ChatWindow, "BASE_NAME_FONT")
    assert hasattr(ChatWindow, "BASE_INPUT_FONT")
    assert hasattr(ChatWindow, "BASE_PADDING")
    assert hasattr(ChatWindow, "BASE_RADIUS")
    assert hasattr(ChatWindow, "BASE_BTN_SIZE")
    assert ChatWindow.BASE_FONT == 17
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_chat_window_scale.py::test_scale_constants_defined -v`
Expected: FAIL

- [ ] **Step 3: 添加基准常量和 _rebuild_stylesheet 方法**

在 `ChatWindow` 类中添加常量：

```python
class ChatWindow(QWidget):
    BASE_WIDTH = 420
    BASE_HEIGHT = 600
    MIN_SCALE = 0.5
    MAX_SCALE = 2.0
    BASE_FONT = 17
    BASE_NAME_FONT = 17
    BASE_INPUT_FONT = 13
    BASE_PADDING = 12
    BASE_RADIUS = 8
    BASE_BTN_SIZE = 34
    BASE_INPUT_HEIGHT = 38
    BASE_SCROLLBAR_WIDTH = 6
    CHARACTER_NAME_COLOR = "#9b3060"
    USER_NAME_COLOR = "#5f6fb2"
```

添加 `_rebuild_stylesheet` 方法：

```python
def _rebuild_stylesheet(self):
    s = self._scale
    font = int(self.BASE_FONT * s)
    name_font = int(self.BASE_NAME_FONT * s)
    input_font = int(self.BASE_INPUT_FONT * s)
    padding = int(self.BASE_PADDING * s)
    radius = int(self.BASE_RADIUS * s)
    btn_size = int(self.BASE_BTN_SIZE * s)
    scrollbar_w = max(4, int(self.BASE_SCROLLBAR_WIDTH * s))

    self._name_label.setStyleSheet(f"""
        color: {self._name_label.styleSheet().split("color:")[1].split(";")[0] if "color:" in self._name_label.styleSheet() else self.CHARACTER_NAME_COLOR};
        font-size: {name_font}px; font-weight: bold; background: transparent;
    """)

    self._dialog_box.setStyleSheet(f"""
        color: #4a3040; font-size: {font}px;
        padding: 2px 0 {padding}px 0; background: transparent;
    """)

    self._input.setStyleSheet(f"""
        QLineEdit {{
            background: rgba(255, 255, 255, 0.7);
            border: 1px solid rgba(220, 160, 180, 0.35);
            border-radius: {radius}px; padding: {int(8*s)}px {padding}px;
            color: #4a3040; font-size: {input_font}px;
        }}
        QLineEdit:focus {{ border-color: #d4567a; }}
    """)

    # 更新按钮尺寸
    for btn in self._panel.findChildren(QPushButton):
        btn.setFixedSize(btn_size, btn_size)
        btn_radius = btn_size // 2
        btn.setStyleSheet(f"""
            QPushButton {{
                background: rgba(255,255,255,0.7); border: 1px solid rgba(220,160,180,0.3);
                border-radius: {btn_radius}px; color: #6b4a5a; font-size: {int(14*s)}px;
            }}
            QPushButton:hover {{ background: rgba(255,200,210,0.6); }}
        """)

    # 更新滚动条宽度
    self._conversation_pane._scroll_area.setStyleSheet(f"""
        QScrollArea {{ background: transparent; border: none; }}
        QScrollBar:vertical {{
            width: {scrollbar_w}px; background: transparent;
        }}
        QScrollBar::handle:vertical {{
            background: rgba(212, 86, 122, 0.4); border-radius: {scrollbar_w//2}px; min-height: 20px;
        }}
        QScrollBar::handle:vertical:hover {{
            background: rgba(212, 86, 122, 0.6);
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0px; }}
        QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}
    """)
```

- [ ] **Step 4: 在 _apply_scale 中调用 _rebuild_stylesheet**

```python
def _apply_scale(self):
    w = int(self.BASE_WIDTH * self._scale)
    h = int(self.BASE_HEIGHT * self._scale)
    self.setFixedSize(w, h)
    panel_h = int(h * 0.50)
    self._panel.setGeometry(10, h - panel_h - 6, w - 20, panel_h)
    self._rebuild_stylesheet()
    self._reload_sprite()
```

- [ ] **Step 5: 更新 _set_dialog_text 使用缩放字号**

```python
def _set_dialog_text(self, text: str) -> None:
    font = int(self.BASE_FONT * self._scale)
    body = escape(text).replace("\n", "<br>")
    self._dialog_box.setText(
        f"<div style='line-height: 145%; color: #4a3040; font-size: {font}px;'>{body}</div>"
    )
    self._conversation_pane.scroll_to_top()
```

- [ ] **Step 6: 更新 _set_speaker_name 使用缩放字号**

```python
def _set_speaker_name(self, name: str, is_user: bool = False) -> None:
    color = self.USER_NAME_COLOR if is_user else self.CHARACTER_NAME_COLOR
    font = int(self.BASE_NAME_FONT * self._scale)
    self._name_label.setText(name)
    self._name_label.setStyleSheet(f"""
        color: {color}; font-size: {font}px; font-weight: bold;
        background: transparent;
    """)
```

- [ ] **Step 7: 运行测试确认通过**

Run: `python -m pytest tests/test_chat_window_scale.py -v`
Expected: ALL PASS

- [ ] **Step 8: 手动验证**

Run: `python main.py`
滚轮缩放桌宠窗口，确认字体、按钮、间距、滚动条全部等比缩放。

- [ ] **Step 9: 提交**

```bash
git add ui/chat/window.py tests/test_chat_window_scale.py
git commit -m "feat: 桌宠窗口全元素等比缩放"
```

---

### Task 8: 最终集成验证

- [ ] **Step 1: 运行全部测试**

Run: `python -m pytest tests/ -q`
Expected: ALL PASS

- [ ] **Step 2: 手动集成测试**

Run: `python main.py`

验证清单：
1. 发送消息 → Agent 日志出现 `[User] 消息` 和 `[角色名] 回复`（带时间戳和颜色）
2. 如果模型支持 thinking → 日志出现灰色斜体 `[Thinking]` 条目
3. 对话框占窗口底部约 50%
4. 发送长消息 → 对话框出现滚动条，可滚动
5. 滚轮缩放 → 字体、按钮、间距全部等比变化
6. 右键菜单放大/缩小/重置 → 同上

- [ ] **Step 3: 提交（如有修复）**

```bash
git add -A
git commit -m "fix: 集成测试修复"
```
