# Chat Window Polish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 优化桌宠聊天窗口的面板宽高比例、立绘落点、毛玻璃透明度、主题描边和多段文本排版，减少空间浪费并保持缩放行为稳定。

**Architecture:** 保持现有 `QLabel + QScrollArea + GlassPanel` 结构不变，只在 `ui/chat/window.py` 内增加更明确的几何参数、样式重建逻辑和显示层文本规范化。测试继续沿用当前仓库的源码检查 + 纯函数行为验证方式，不引入新的 UI 测试框架。

**Tech Stack:** Python 3.11+, PySide6, pytest, 现有聊天窗口实现

---

## 文件结构

| 文件 | 职责 |
|------|------|
| `ui/chat/window.py` | 聊天窗口布局、毛玻璃绘制、缩放样式、文本显示规范化 |
| `tests/test_chat_window_scale.py` | 聊天窗口布局比例、样式钩子和文本规范化回归测试 |

---

### Task 1: 补齐聊天窗口优化回归测试

**Files:**
- Modify: `tests/test_chat_window_scale.py:1-30`
- Modify: `ui/chat/window.py:99-340`

- [ ] **Step 1: 写失败测试，覆盖新布局参数和文本规范化入口**

```python
import inspect


def test_chat_window_width_and_panel_ratio_updated():
    """聊天窗口应更宽，面板高度应缩短到 45%。"""
    import ui.chat.window as win_module

    assert win_module.ChatWindow.BASE_WIDTH == 500
    source = inspect.getsource(win_module.ChatWindow._apply_scale)
    assert "0.45" in source or "0.45)" in source


def test_reload_sprite_uses_lower_visual_anchor():
    """立绘重载目标应更高，以便视觉上整体下沉。"""
    import ui.chat.window as win_module

    source = inspect.getsource(win_module.ChatWindow._reload_sprite)
    assert "0.92" in source or "0.92)" in source


def test_dialog_text_normalization_collapses_extra_blank_lines():
    """显示层应压缩多余空行，但保留段落分隔。"""
    from ui.chat.window import ChatWindow

    raw = "\n\n第一段\n\n\n第二段\n\n\n\n第三段\n\n"
    normalized = ChatWindow._normalize_dialog_text(raw)
    assert normalized == "第一段\n\n第二段\n\n第三段"


def test_dialog_html_uses_tighter_line_height_and_paragraph_gap():
    """HTML 渲染应收紧行高，并用小段距代替整行空白。"""
    from ui.chat.window import ChatWindow

    html = ChatWindow._build_dialog_html("第一段\n\n第二段", font=17, line_height=132, paragraph_gap=4)
    assert "line-height: 132%" in html
    assert "margin:0 0 4px 0;" in html
    assert "<br><br><br>" not in html


def test_rebuild_stylesheet_contains_layered_theme_borders():
    """输入框和按钮样式应包含更明显的主题描边层次。"""
    import ui.chat.window as win_module

    source = inspect.getsource(win_module.ChatWindow._rebuild_stylesheet)
    assert "rgba(212, 86, 122, 0.32)" in source
    assert "rgba(155, 48, 96, 0.18)" in source
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_chat_window_scale.py -v`
Expected: FAIL，至少出现以下一种错误：
- `assert 420 == 500`
- `AttributeError: type object 'ChatWindow' has no attribute '_normalize_dialog_text'`
- `AttributeError: type object 'ChatWindow' has no attribute '_build_dialog_html'`

- [ ] **Step 3: 提交测试变更**

```bash
git add tests/test_chat_window_scale.py
git commit -m "test: add chat window polish regression coverage"
```

---

### Task 2: 调整聊天窗口几何比例和立绘落点

**Files:**
- Modify: `ui/chat/window.py:99-340`
- Test: `tests/test_chat_window_scale.py`

- [ ] **Step 1: 写最小实现，更新窗口宽度、面板比例和立绘目标高度**

```python
class ChatWindow(QWidget):
    """Desktop pet style chat window — frameless, transparent, draggable."""

    BASE_WIDTH = 500
    BASE_HEIGHT = 600
    MIN_SCALE = 0.5
    MAX_SCALE = 2.0
    BASE_FONT = 17
    BASE_NAME_FONT = 17
    BASE_INPUT_FONT = 13
    BASE_PADDING = 12
    BASE_RADIUS = 8
    BASE_BTN_SIZE = 34
    BASE_SCROLLBAR_WIDTH = 6
    CHARACTER_NAME_COLOR = "#9b3060"
    USER_NAME_COLOR = "#5f6fb2"

    def _apply_scale(self):
        w = int(self.BASE_WIDTH * self._scale)
        h = int(self.BASE_HEIGHT * self._scale)
        self.setFixedSize(w, h)
        panel_h = int(h * 0.45)
        panel_x = max(6, int(8 * self._scale))
        panel_bottom = max(4, int(4 * self._scale))
        self._panel.setGeometry(panel_x, h - panel_h - panel_bottom, w - panel_x * 2, panel_h)
        self._rebuild_stylesheet()
        self._reload_sprite()

    def _reload_sprite(self):
        """Reload sprite at current scale."""
        sprite_area_h = int(self.height() * 0.92)
        self._sprite_label.setFixedHeight(self.height())
        self._sprite_label.setContentsMargins(0, 0, 0, -max(10, int(22 * self._scale)))
        target_size = QSize(int(self.width() * 1.04), sprite_area_h)
        self._sprite_mgr.reload(target_size)
```

- [ ] **Step 2: 收紧面板内部留白，避免高度缩短后显得局促**

```python
def _setup_ui(self):
    # Glass panel at bottom
    self._panel = GlassPanel(self)
    panel_layout = QVBoxLayout(self._panel)
    panel_layout.setContentsMargins(18, 14, 18, 14)
    panel_layout.setSpacing(7)

    self._conversation_pane = ConversationPane()
    ...
```

- [ ] **Step 3: 运行测试确认布局相关断言通过**

Run: `python -m pytest tests/test_chat_window_scale.py::test_chat_window_width_and_panel_ratio_updated tests/test_chat_window_scale.py::test_reload_sprite_uses_lower_visual_anchor -v`
Expected: PASS

- [ ] **Step 4: 提交几何改动**

```bash
git add ui/chat/window.py
git commit -m "feat: widen chat panel and lower sprite anchor"
```

---

### Task 3: 增强毛玻璃、输入框和按钮的主题层次

**Files:**
- Modify: `ui/chat/window.py:34-45`
- Modify: `ui/chat/window.py:195-333`
- Test: `tests/test_chat_window_scale.py`

- [ ] **Step 1: 调整 GlassPanel 绘制，降低填充透明度并增加双层描边**

```python
class GlassPanel(QWidget):
    """Frosted glass panel drawn with rounded rect + semi-transparent fill."""

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        outer_rect = self.rect().adjusted(1, 1, -1, -1)
        inner_rect = self.rect().adjusted(2, 2, -2, -2)

        outer_path = QPainterPath()
        outer_path.addRoundedRect(outer_rect, 16, 16)
        inner_path = QPainterPath()
        inner_path.addRoundedRect(inner_rect, 15, 15)

        p.fillPath(outer_path, QBrush(QColor(255, 245, 250, 168)))
        p.setPen(QColor(212, 86, 122, 82))
        p.drawPath(outer_path)
        p.setPen(QColor(255, 255, 255, 92))
        p.drawPath(inner_path)
        p.end()
```

- [ ] **Step 2: 更新输入框、按钮和滚动条样式，加入更细的主题边缘层次**

```python
def _circle_btn_style(
    self,
    bg="rgba(255,255,255,0.68)",
    hover="rgba(255,214,224,0.82)",
    border="rgba(212, 86, 122, 0.32)",
):
    return f"""
        QPushButton {{
            background: {bg};
            border: 1px solid {border};
            border-radius: 17px;
            color: #6b4a5a;
            font-size: 14px;
        }}
        QPushButton:hover {{
            background: {hover};
            border-color: rgba(155, 48, 96, 0.42);
        }}
    """


def _rebuild_stylesheet(self):
    s = self._scale
    font = int(self.BASE_FONT * s)
    input_font = int(self.BASE_INPUT_FONT * s)
    padding = int(self.BASE_PADDING * s)
    radius = int(self.BASE_RADIUS * s)
    btn_size = int(self.BASE_BTN_SIZE * s)
    scrollbar_w = max(4, int(self.BASE_SCROLLBAR_WIDTH * s))

    self._input.setStyleSheet(f"""
        QLineEdit {{
            background: rgba(255, 255, 255, 0.64);
            border: 1px solid rgba(212, 86, 122, 0.32);
            border-top: 1px solid rgba(255, 255, 255, 0.72);
            border-bottom: 1px solid rgba(155, 48, 96, 0.18);
            border-radius: {radius}px;
            padding: {int(8 * s)}px {padding}px;
            color: #4a3040;
            font-size: {input_font}px;
        }}
        QLineEdit:focus {{
            border-color: rgba(155, 48, 96, 0.56);
            background: rgba(255, 252, 254, 0.78);
        }}
    """)

    for btn in self._panel.findChildren(QPushButton):
        btn.setFixedSize(btn_size, btn_size)
        btn_radius = btn_size // 2
        btn.setStyleSheet(f"""
            QPushButton {{
                background: rgba(255,255,255,0.68);
                border: 1px solid rgba(212, 86, 122, 0.32);
                border-top: 1px solid rgba(255, 255, 255, 0.74);
                border-bottom: 1px solid rgba(155, 48, 96, 0.18);
                border-radius: {btn_radius}px;
                color: #6b4a5a;
                font-size: {int(14 * s)}px;
            }}
            QPushButton:hover {{
                background: rgba(255,214,224,0.82);
                border-color: rgba(155, 48, 96, 0.42);
            }}
        """)

    self._conversation_pane._scroll_area.setStyleSheet(f"""
        QScrollArea {{ background: transparent; border: none; }}
        QScrollBar:vertical {{
            width: {scrollbar_w}px;
            background: rgba(255, 255, 255, 0.12);
        }}
        QScrollBar::handle:vertical {{
            background: rgba(212, 86, 122, 0.36);
            border-radius: {scrollbar_w // 2}px;
            min-height: 20px;
        }}
        QScrollBar::handle:vertical:hover {{
            background: rgba(155, 48, 96, 0.48);
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0px; }}
        QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}
    """)
```

- [ ] **Step 3: 运行样式断言**

Run: `python -m pytest tests/test_chat_window_scale.py::test_rebuild_stylesheet_contains_layered_theme_borders -v`
Expected: PASS

- [ ] **Step 4: 提交视觉样式改动**

```bash
git add ui/chat/window.py
git commit -m "feat: refine chat window glass and theme borders"
```

---

### Task 4: 规范化多段文本显示并收紧行距

**Files:**
- Modify: `ui/chat/window.py:3-3`
- Modify: `ui/chat/window.py:267-273`
- Test: `tests/test_chat_window_scale.py`

- [ ] **Step 1: 增加文本规范化和 HTML 构造静态方法**

```python
import re
from html import escape


class ChatWindow(QWidget):
    ...

    @staticmethod
    def _normalize_dialog_text(text: str) -> str:
        normalized = text.strip()
        return re.sub(r"\n{3,}", "\n\n", normalized)

    @staticmethod
    def _build_dialog_html(
        text: str,
        font: int,
        line_height: int = 132,
        paragraph_gap: int = 4,
    ) -> str:
        normalized = ChatWindow._normalize_dialog_text(text)
        if not normalized:
            return (
                f"<div style='line-height: {line_height}%; color: #4a3040; "
                f"font-size: {font}px; margin:0;'></div>"
            )

        paragraphs = normalized.split("\n\n")
        html_parts = []
        for index, paragraph in enumerate(paragraphs):
            margin = "0" if index == len(paragraphs) - 1 else f"0 0 {paragraph_gap}px 0"
            body = escape(paragraph).replace("\n", "<br>")
            html_parts.append(f"<div style='margin:{margin};'>{body}</div>")

        return (
            f"<div style='line-height: {line_height}%; color: #4a3040; "
            f"font-size: {font}px;'>{''.join(html_parts)}</div>"
        )
```

- [ ] **Step 2: 在 `_set_dialog_text` 中使用新 HTML，收紧行距并避免额外空白**

```python
def _set_dialog_text(self, text: str) -> None:
    font = int(self.BASE_FONT * self._scale)
    paragraph_gap = max(2, int(4 * self._scale))
    html = self._build_dialog_html(
        text,
        font=font,
        line_height=132,
        paragraph_gap=paragraph_gap,
    )
    self._dialog_box.setText(html)
    self._conversation_pane.scroll_to_top()
```

- [ ] **Step 3: 同步正文基础样式，减少底部 padding**

```python
self._dialog_box.setStyleSheet(f"""
    color: #4a3040;
    font-size: {font}px;
    padding: 1px 0 {max(4, int(6 * s))}px 0;
    background: transparent;
""")
```

- [ ] **Step 4: 运行文本相关测试**

Run: `python -m pytest tests/test_chat_window_scale.py::test_dialog_text_normalization_collapses_extra_blank_lines tests/test_chat_window_scale.py::test_dialog_html_uses_tighter_line_height_and_paragraph_gap -v`
Expected: PASS

- [ ] **Step 5: 提交文本排版改动**

```bash
git add ui/chat/window.py
git commit -m "fix: tighten chat dialog paragraph spacing"
```

---

### Task 5: 集成验证与文档同步

**Files:**
- Modify: `CLAUDE.md`
- Modify: `docs/README.md`
- Modify: `docs/ui-guidelines.md`
- Test: `tests/test_chat_window_scale.py`

- [ ] **Step 1: 更新协作文档和 UI 规范摘要**

```markdown
# CLAUDE.md
- 第三阶段聊天窗优化：
  - 面板体感更宽、面板高度收紧
  - 立绘落点下移，底部与面板形成轻微遮挡关系
  - 聊天文本压缩多余段间空白

# docs/README.md
- 当前进度补充：
  - 桌宠聊天窗视觉与排版优化（更宽面板、更轻毛玻璃、更紧凑多段文本）

# docs/ui-guidelines.md
### 聊天窗规范
- 底部毛玻璃对话面板应保持较宽的横向占比，避免过多左右留白
- 角色立绘可与面板形成轻微前后遮挡关系，但不得影响文字可读性
- 多段回复应保留段落语义，但不得使用浪费空间的整行空白分隔
```

- [ ] **Step 2: 运行自动化验证**

Run: `python -m pytest tests/test_chat_window_scale.py -v`
Expected: PASS

Run: `python -m pytest tests/ -q`
Expected: PASS

Run: `python -m py_compile ui/chat/window.py`
Expected: no output

- [ ] **Step 3: 运行手动验证**

Run: `python main.py`

验证清单：
1. 底部面板比当前更宽，整体高度较当前更矮
2. 角色立绘视觉上更靠下，底部略低于面板上缘
3. 毛玻璃更通透，但文字仍清晰可读
4. 输入框和按钮边缘有更明显的樱花主题层次
5. 多段 LLM 回复不再出现空一整行的浪费
6. 鼠标滚轮缩放和右键缩放后，样式比例仍协调

- [ ] **Step 4: 提交最终改动**

```bash
git add CLAUDE.md docs/README.md docs/ui-guidelines.md ui/chat/window.py tests/test_chat_window_scale.py
git commit -m "feat: polish chat window layout and paragraph spacing"
```
