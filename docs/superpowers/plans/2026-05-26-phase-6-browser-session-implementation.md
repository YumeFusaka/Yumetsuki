# Phase 6 Browser Session Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** 将 `web_automation` 从单次搜索 / 提取 / 截图扩展为具备持续浏览器会话的受控页面操控能力。

**Architecture:** 继续使用本地插件 `plugins/web_automation/` 和 Playwright，不接入通用自治代理框架。新增 `BrowserSessionController` 维护单个可见或 headless Playwright 会话，插件工具只暴露明确动作：打开、导航、点击、填写、等待、提取、状态、关闭；所有动作使用配置化超时并返回可进入 LLM 上下文的结构化文本。

**Tech Stack:** Python 3、Playwright sync API、pytest、Pydantic、现有插件 SDK。

---

## 文件结构

- 修改 `config/schema.py`
  - 扩展 `WebAutomationConfig`：浏览器默认超时、页面等待超时、会话截图目录、会话 headless 默认值和提取长度上限。
- 修改 `plugins/web_automation/browser.py`
  - 现有 `run_headless()` / `run_visible()` 保持兼容。
  - 新增 `BrowserSessionController`，负责持续浏览器生命周期。
- 创建 `plugins/web_automation/session.py`
  - 定义 `BrowserSessionState`、`BrowserActionResult` 和页面状态摘要格式化。
- 修改 `plugins/web_automation/page.py`
  - 增加当前页面动作 helper：`navigate_current()`、`click_selector()`、`fill_selector()`、`wait_for_selector()`、`extract_current_text()`。
- 修改 `plugins/web_automation/plugin.py`
  - 新增会话工具：`web_session_open`、`web_session_navigate`、`web_session_click`、`web_session_fill`、`web_session_wait`、`web_session_extract`、`web_session_status`、`web_session_close`。
  - 保留现有 `web_search`、`web_search_visible`、`web_extract`、`web_screenshot` 行为。
- 修改测试：
  - `tests/test_web_automation.py`
  - 新增 `tests/test_web_automation_session.py`
- 修改文档：
  - `docs/plugin-web-automation.md`
  - `docs/architecture.md`
  - `docs/development.md`
  - `CLAUDE.md`

---

### Task 1: WebAutomationConfig 增加浏览器会话参数

**Files:**
- Modify: `config/schema.py`
- Test: `tests/test_web_automation.py`

- [x] **Step 1: Write failing config tests**

Update `tests/test_web_automation.py::test_web_automation_config_defaults`:

```python
def test_web_automation_config_defaults():
    config = WebAutomationConfig()
    assert config.permission_level == "medium"
    assert config.default_engine == "bing"
    assert config.screenshot_dir == "data/screenshots"
    assert config.browser_headless is False
    assert config.browser_timeout_ms == 15000
    assert config.page_wait_timeout_ms == 10000
    assert config.session_screenshot_dir == "data/browser_sessions"
    assert config.max_extract_length == 4000
```

- [x] **Step 2: Run test and verify RED**

Run:

```bash
python -m pytest tests/test_web_automation.py::test_web_automation_config_defaults -q
```

Expected: FAIL because these config fields do not exist.

- [x] **Step 3: Implement config fields**

Update `config/schema.py`:

```python
class WebAutomationConfig(BaseModel):
    permission_level: str = "medium"
    default_engine: str = "bing"
    screenshot_dir: str = "data/screenshots"
    browser_headless: bool = False
    browser_timeout_ms: int = 15000
    page_wait_timeout_ms: int = 10000
    session_screenshot_dir: str = "data/browser_sessions"
    max_extract_length: int = 4000
```

- [x] **Step 4: Run config test**

Run:

```bash
python -m pytest tests/test_web_automation.py::test_web_automation_config_defaults -q
```

Expected: PASS.

---

### Task 2: 定义浏览器会话结果模型

**Files:**
- Create: `plugins/web_automation/session.py`
- Test: `tests/test_web_automation_session.py`

- [x] **Step 1: Write failing model tests**

Create `tests/test_web_automation_session.py`:

```python
from plugins.web_automation.session import BrowserActionResult, BrowserSessionState, format_state_summary


def test_browser_action_result_formats_success():
    result = BrowserActionResult(
        ok=True,
        action="navigate",
        message="已打开页面",
        url="https://example.com",
        title="Example",
        text_preview="页面文本",
    )

    text = result.to_text()

    assert "动作：navigate" in text
    assert "状态：成功" in text
    assert "URL：https://example.com" in text
    assert "标题：Example" in text
    assert "页面文本" in text


def test_format_state_summary_for_closed_session():
    state = BrowserSessionState(is_open=False)

    assert format_state_summary(state) == "浏览器会话未打开。"
```

- [x] **Step 2: Run tests and verify RED**

Run:

```bash
python -m pytest tests/test_web_automation_session.py -q
```

Expected: FAIL because `plugins.web_automation.session` does not exist.

- [x] **Step 3: Implement session result models**

Create `plugins/web_automation/session.py`:

```python
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BrowserSessionState:
    is_open: bool
    url: str = ""
    title: str = ""


@dataclass(frozen=True)
class BrowserActionResult:
    ok: bool
    action: str
    message: str
    url: str = ""
    title: str = ""
    text_preview: str = ""

    def to_text(self) -> str:
        state = "成功" if self.ok else "失败"
        lines = [
            f"动作：{self.action}",
            f"状态：{state}",
            f"消息：{self.message}",
        ]
        if self.url:
            lines.append(f"URL：{self.url}")
        if self.title:
            lines.append(f"标题：{self.title}")
        if self.text_preview:
            lines.append("页面摘要：")
            lines.append(self.text_preview)
        return "\n".join(lines)


def format_state_summary(state: BrowserSessionState) -> str:
    if not state.is_open:
        return "浏览器会话未打开。"
    lines = ["浏览器会话已打开。"]
    if state.url:
        lines.append(f"URL：{state.url}")
    if state.title:
        lines.append(f"标题：{state.title}")
    return "\n".join(lines)
```

- [x] **Step 4: Run model tests**

Run:

```bash
python -m pytest tests/test_web_automation_session.py -q
```

Expected: PASS.

---

### Task 3: 增加当前页面动作 helper

**Files:**
- Modify: `plugins/web_automation/page.py`
- Test: `tests/test_web_automation_session.py`

- [x] **Step 1: Write failing page action tests**

Append to `tests/test_web_automation_session.py`:

```python
from unittest.mock import MagicMock

from plugins.web_automation.page import click_selector, extract_current_text, fill_selector, navigate_current, wait_for_selector


def test_navigate_current_uses_domcontentloaded_timeout():
    page = MagicMock()
    page.url = "https://example.com"
    page.title.return_value = "Example"

    result = navigate_current(page, "https://example.com", timeout_ms=1234)

    page.goto.assert_called_once_with("https://example.com", wait_until="domcontentloaded", timeout=1234)
    assert result.ok is True
    assert result.url == "https://example.com"
    assert result.title == "Example"


def test_click_fill_wait_helpers_use_timeout():
    page = MagicMock()
    page.url = "https://example.com/form"
    page.title.return_value = "Form"

    click = click_selector(page, "#submit", timeout_ms=100)
    fill = fill_selector(page, "#name", "梦月", timeout_ms=200)
    wait = wait_for_selector(page, ".done", timeout_ms=300)

    page.click.assert_called_once_with("#submit", timeout=100)
    page.fill.assert_called_once_with("#name", "梦月", timeout=200)
    page.wait_for_selector.assert_called_once_with(".done", timeout=300)
    assert click.ok and fill.ok and wait.ok


def test_extract_current_text_truncates_text():
    page = MagicMock()
    page.url = "https://example.com"
    page.title.return_value = "Example"
    page.evaluate.return_value = "第一行\\n\\n第二行很长"

    result = extract_current_text(page, max_length=4)

    assert result.ok is True
    assert "第一行" in result.text_preview
    assert "内容已截断" in result.text_preview
```

- [x] **Step 2: Run tests and verify RED**

Run:

```bash
python -m pytest tests/test_web_automation_session.py -q
```

Expected: FAIL because page action helpers do not exist.

- [x] **Step 3: Implement page action helpers**

Add to `plugins/web_automation/page.py`:

```python
from plugins.web_automation.session import BrowserActionResult


def _page_title(page: Any) -> str:
    try:
        return page.title()
    except Exception:
        return ""


def _current_url(page: Any) -> str:
    return getattr(page, "url", "") or ""


def navigate_current(page: Any, url: str, timeout_ms: int = 15000) -> BrowserActionResult:
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
        return BrowserActionResult(True, "navigate", "已打开页面", _current_url(page), _page_title(page))
    except Exception as exc:
        return BrowserActionResult(False, "navigate", f"打开页面失败：{exc}", _current_url(page), _page_title(page))


def click_selector(page: Any, selector: str, timeout_ms: int = 10000) -> BrowserActionResult:
    try:
        page.click(selector, timeout=timeout_ms)
        return BrowserActionResult(True, "click", f"已点击：{selector}", _current_url(page), _page_title(page))
    except Exception as exc:
        return BrowserActionResult(False, "click", f"点击失败：{exc}", _current_url(page), _page_title(page))


def fill_selector(page: Any, selector: str, text: str, timeout_ms: int = 10000) -> BrowserActionResult:
    try:
        page.fill(selector, text, timeout=timeout_ms)
        return BrowserActionResult(True, "fill", f"已填写：{selector}", _current_url(page), _page_title(page))
    except Exception as exc:
        return BrowserActionResult(False, "fill", f"填写失败：{exc}", _current_url(page), _page_title(page))


def wait_for_selector(page: Any, selector: str, timeout_ms: int = 10000) -> BrowserActionResult:
    try:
        page.wait_for_selector(selector, timeout=timeout_ms)
        return BrowserActionResult(True, "wait", f"已等待到元素：{selector}", _current_url(page), _page_title(page))
    except Exception as exc:
        return BrowserActionResult(False, "wait", f"等待失败：{exc}", _current_url(page), _page_title(page))


def extract_current_text(page: Any, max_length: int = 4000) -> BrowserActionResult:
    try:
        text = page.evaluate(_EXTRACT_JS)
        text = "\n".join(line.strip() for line in text.splitlines() if line.strip())
        if len(text) > max_length:
            text = text[:max_length] + "\n...(内容已截断)"
        return BrowserActionResult(
            True,
            "extract",
            "已提取当前页面文本",
            _current_url(page),
            _page_title(page),
            text or "页面无文本内容",
        )
    except Exception as exc:
        return BrowserActionResult(False, "extract", f"提取失败：{exc}", _current_url(page), _page_title(page))
```

- [x] **Step 4: Run page helper tests**

Run:

```bash
python -m pytest tests/test_web_automation_session.py -q
```

Expected: PASS.

---

### Task 4: 实现 BrowserSessionController 生命周期

**Files:**
- Modify: `plugins/web_automation/browser.py`
- Test: `tests/test_web_automation_session.py`

- [x] **Step 1: Write failing controller tests**

Append to `tests/test_web_automation_session.py`:

```python
from plugins.web_automation.browser import BrowserSessionController


class FakePlaywright:
    def __init__(self):
        self.chromium = MagicMock()
        self.browser = MagicMock()
        self.page = MagicMock()
        self.page.url = "about:blank"
        self.page.title.return_value = ""
        self.chromium.launch.return_value = self.browser
        self.browser.new_page.return_value = self.page

    def stop(self):
        self.stopped = True


def test_browser_session_controller_open_status_close():
    fake_pw = FakePlaywright()
    controller = BrowserSessionController(playwright_factory=lambda: fake_pw)

    text = controller.open(headless=False, timeout_ms=15000)
    status = controller.status()
    close = controller.close()

    fake_pw.chromium.launch.assert_called_once_with(channel="msedge", headless=False)
    assert "浏览器会话已打开" in text
    assert "浏览器会话已打开" in status
    assert "浏览器会话已关闭" in close
    fake_pw.browser.close.assert_called_once()


def test_browser_session_controller_reuses_open_session():
    fake_pw = FakePlaywright()
    controller = BrowserSessionController(playwright_factory=lambda: fake_pw)

    controller.open(headless=True, timeout_ms=15000)
    second = controller.open(headless=True, timeout_ms=15000)

    assert fake_pw.chromium.launch.call_count == 1
    assert "浏览器会话已打开" in second
```

- [x] **Step 2: Run tests and verify RED**

Run:

```bash
python -m pytest tests/test_web_automation_session.py::test_browser_session_controller_open_status_close tests/test_web_automation_session.py::test_browser_session_controller_reuses_open_session -q
```

Expected: FAIL because `BrowserSessionController` does not exist.

- [x] **Step 3: Implement controller**

Add to `plugins/web_automation/browser.py`:

```python
from plugins.web_automation.session import BrowserSessionState, format_state_summary


class BrowserSessionController:
    def __init__(self, playwright_factory=None):
        self._playwright_factory = playwright_factory
        self._playwright = None
        self._browser = None
        self._page = None

    def open(self, headless: bool = False, timeout_ms: int = 15000) -> str:
        if self._page is not None:
            return self.status()
        if self._playwright_factory is None:
            from playwright.sync_api import sync_playwright
            self._playwright = sync_playwright().start()
        else:
            self._playwright = self._playwright_factory()
        self._browser = self._playwright.chromium.launch(channel="msedge", headless=headless)
        self._page = self._browser.new_page()
        self._page.set_default_timeout(timeout_ms)
        return self.status()

    def page(self):
        if self._page is None:
            raise RuntimeError("浏览器会话未打开")
        return self._page

    def status(self) -> str:
        if self._page is None:
            return format_state_summary(BrowserSessionState(is_open=False))
        return format_state_summary(BrowserSessionState(
            is_open=True,
            url=getattr(self._page, "url", "") or "",
            title=self._safe_title(),
        ))

    def close(self) -> str:
        if self._browser is not None:
            self._browser.close()
        if self._playwright is not None and hasattr(self._playwright, "stop"):
            self._playwright.stop()
        self._browser = None
        self._page = None
        self._playwright = None
        return "浏览器会话已关闭。"

    def _safe_title(self) -> str:
        try:
            return self._page.title() if self._page is not None else ""
        except Exception:
            return ""
```

- [x] **Step 4: Run controller tests**

Run:

```bash
python -m pytest tests/test_web_automation_session.py -q
```

Expected: PASS.

---

### Task 5: Web 自动化插件暴露会话工具

**Files:**
- Modify: `plugins/web_automation/plugin.py`
- Test: `tests/test_web_automation.py`
- Test: `tests/test_web_automation_session.py`

- [x] **Step 1: Write failing plugin tool tests**

Add to `tests/test_web_automation.py`:

```python
def test_wa_plugin_has_browser_session_tools():
    plugin = Plugin()
    tool_names = [t.name for t in plugin.tools()]

    assert "web_session_open" in tool_names
    assert "web_session_navigate" in tool_names
    assert "web_session_click" in tool_names
    assert "web_session_fill" in tool_names
    assert "web_session_wait" in tool_names
    assert "web_session_extract" in tool_names
    assert "web_session_status" in tool_names
    assert "web_session_close" in tool_names
```

Add to `tests/test_web_automation_session.py`:

```python
def test_web_session_tools_call_controller(monkeypatch):
    plugin = Plugin()
    fake = MagicMock()
    fake.open.return_value = "opened"
    fake.status.return_value = "status"
    fake.close.return_value = "closed"
    monkeypatch.setattr(plugin, "_session", fake)

    assert plugin.call_tool("web_session_open", {"headless": True}) == "opened"
    assert plugin.call_tool("web_session_status", {}) == "status"
    assert plugin.call_tool("web_session_close", {}) == "closed"
    fake.open.assert_called_once()
```

- [x] **Step 2: Run tests and verify RED**

Run:

```bash
python -m pytest tests/test_web_automation.py::test_wa_plugin_has_browser_session_tools tests/test_web_automation_session.py::test_web_session_tools_call_controller -q
```

Expected: FAIL because session tools do not exist.

- [x] **Step 3: Add controller to Plugin.__init__()**

Update imports in `plugins/web_automation/plugin.py`:

```python
from plugins.web_automation.browser import BrowserSessionController, run_headless, run_visible
from plugins.web_automation.page import (
    click_selector,
    extract_current_text,
    fill_selector,
    navigate_current,
    wait_for_selector,
)
```

Update `Plugin.__init__()`:

```python
self._browser_headless = bool(config.get("browser_headless", False))
self._browser_timeout_ms = int(config.get("browser_timeout_ms", 15000))
self._page_wait_timeout_ms = int(config.get("page_wait_timeout_ms", 10000))
self._max_extract_length = int(config.get("max_extract_length", 4000))
self._session = BrowserSessionController()
```

- [x] **Step 4: Add session tools**

Add methods to `Plugin`:

```python
@tool(description="打开一个由 Playwright 控制的持续浏览器会话", params={"headless": "是否无头运行，默认使用配置值"})
def web_session_open(self, headless: bool = False) -> str:
    denied = self._check_permission(PermissionLevel.MEDIUM)
    if denied:
        return denied
    return self._session.open(headless=bool(headless or self._browser_headless), timeout_ms=self._browser_timeout_ms)


@tool(description="在持续浏览器会话中导航到指定 URL", params={"url": "要打开的 URL"})
def web_session_navigate(self, url: str) -> str:
    denied = self._check_permission(PermissionLevel.MEDIUM)
    if denied:
        return denied
    return navigate_current(self._session.page(), url, timeout_ms=self._browser_timeout_ms).to_text()


@tool(description="点击当前页面中的 CSS selector 元素", params={"selector": "CSS selector"})
def web_session_click(self, selector: str) -> str:
    denied = self._check_permission(PermissionLevel.HIGH)
    if denied:
        return denied
    return click_selector(self._session.page(), selector, timeout_ms=self._page_wait_timeout_ms).to_text()


@tool(description="填写当前页面中的 CSS selector 输入框", params={"selector": "CSS selector", "text": "要填写的文本"})
def web_session_fill(self, selector: str, text: str) -> str:
    denied = self._check_permission(PermissionLevel.HIGH)
    if denied:
        return denied
    return fill_selector(self._session.page(), selector, text, timeout_ms=self._page_wait_timeout_ms).to_text()


@tool(description="等待当前页面出现指定 CSS selector 元素", params={"selector": "CSS selector"})
def web_session_wait(self, selector: str) -> str:
    denied = self._check_permission(PermissionLevel.MEDIUM)
    if denied:
        return denied
    return wait_for_selector(self._session.page(), selector, timeout_ms=self._page_wait_timeout_ms).to_text()


@tool(description="提取当前浏览器会话页面的可见文本", params={"max_length": "最大返回字符数，默认使用配置值"})
def web_session_extract(self, max_length: int = 0) -> str:
    denied = self._check_permission(PermissionLevel.MEDIUM)
    if denied:
        return denied
    limit = int(max_length or self._max_extract_length)
    return extract_current_text(self._session.page(), max_length=limit).to_text()


@tool(description="查看当前持续浏览器会话状态")
def web_session_status(self) -> str:
    denied = self._check_permission(PermissionLevel.LOW)
    if denied:
        return denied
    return self._session.status()


@tool(description="关闭当前持续浏览器会话")
def web_session_close(self) -> str:
    denied = self._check_permission(PermissionLevel.MEDIUM)
    if denied:
        return denied
    return self._session.close()
```

- [x] **Step 5: Run plugin tests**

Run:

```bash
python -m pytest tests/test_web_automation.py tests/test_web_automation_session.py -q
```

Expected: PASS.

---

### Task 6: 文档同步

**Files:**
- Modify: `docs/plugin-web-automation.md`
- Modify: `docs/architecture.md`
- Modify: `docs/development.md`
- Modify: `CLAUDE.md`

- [x] **Step 1: Update docs**

Document these facts:

- `web_automation` 仍保留后台搜索、可见搜索、页面提取、截图。
- 新增持续浏览器会话工具，支持打开、导航、点击、填写、等待、提取、状态和关闭。
- 点击和填写属于高权限操作；导航、等待、提取属于中权限操作；状态属于低权限操作。
- 配置项：`browser_headless`、`browser_timeout_ms`、`page_wait_timeout_ms`、`session_screenshot_dir`、`max_extract_length`。
- 持续会话是 Playwright 控制的浏览器，不复用用户系统默认浏览器窗口。

- [x] **Step 2: Run docs scan**

Run:

```bash
rg -n "web_session_open|web_session_navigate|browser_timeout_ms|持续浏览器会话|Playwright 控制" CLAUDE.md docs
```

Expected: matches in updated docs.

---

### Task 7: Final verification

**Files:**
- All changed files

- [x] **Step 1: Focused tests**

Run:

```bash
python -m pytest tests/test_web_automation.py tests/test_web_automation_session.py -q
```

Expected: PASS.

- [x] **Step 2: Syntax check**

Run:

```bash
python -m py_compile config/schema.py plugins/web_automation/browser.py plugins/web_automation/page.py plugins/web_automation/plugin.py plugins/web_automation/session.py
```

Expected: exit code 0.

- [x] **Step 3: Full tests**

Run:

```bash
python -m pytest tests/ -q
```

Expected: PASS.

- [x] **Step 4: Diff check**

Run:

```bash
git diff --check
```

Expected: exit code 0.
