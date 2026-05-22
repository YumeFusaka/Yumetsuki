# Web 自动化插件实现计划（第一期）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 AI 添加浏览器自动化能力（搜索、提取文本、截图），基于 Playwright + Edge，支持 headless 和可见两种模式。

**Architecture:** 新插件 `plugins/web_automation/`，内部分模块：browser.py（浏览器生命周期）、search.py（搜索引擎）、page.py（页面操作）、plugin.py（入口+权限）。使用 playwright.sync_api 同步调用。

**Tech Stack:** Python, Playwright (sync_api), Edge (msedge channel), Pydantic, pytest

---

## 文件结构

| 文件 | 职责 |
|------|------|
| `plugins/web_automation/__init__.py` | 空包初始化 |
| `plugins/web_automation/browser.py` | Playwright 浏览器启动/关闭（headless/visible） |
| `plugins/web_automation/search.py` | Bing/Google 搜索结果提取 |
| `plugins/web_automation/page.py` | 页面文本提取、截图 |
| `plugins/web_automation/plugin.py` | Plugin 入口，@tool 方法，权限检查 |
| `plugins/web_automation/README.md` | 插件自述 |
| `config/schema.py` | 新增 WebAutomationConfig |
| `tests/test_web_automation.py` | 单元测试 |
| `docs/plugin-web-automation.md` | 插件说明文档 |

---

## Task 1: 安装依赖 + 添加 WebAutomationConfig

**Files:**
- Modify: `config/schema.py`
- Modify: `requirements.txt`（如存在）
- Create: `tests/test_web_automation.py`

- [ ] **Step 1: 安装 playwright**

```bash
pip install playwright
playwright install msedge
```

- [ ] **Step 2: 写配置测试**

创建 `tests/test_web_automation.py`：

```python
from config.schema import AgentConfig, WebAutomationConfig


def test_web_automation_config_defaults():
    config = WebAutomationConfig()
    assert config.permission_level == "medium"
    assert config.default_engine == "bing"
    assert config.screenshot_dir == "data/screenshots"


def test_web_automation_config_in_agent_config():
    agent = AgentConfig()
    assert agent.web_automation.permission_level == "medium"
    assert agent.web_automation.default_engine == "bing"
```

- [ ] **Step 3: 运行测试确认失败**

Run: `python -m pytest tests/test_web_automation.py -v`
Expected: FAIL（WebAutomationConfig 未定义）

- [ ] **Step 4: 实现 WebAutomationConfig**

在 `config/schema.py` 的 `SystemControlConfig` 之后添加：

```python
class WebAutomationConfig(BaseModel):
    permission_level: str = "medium"
    default_engine: str = "bing"
    screenshot_dir: str = "data/screenshots"
```

在 `AgentConfig` 中添加字段：

```python
class AgentConfig(BaseModel):
    planner: PlannerConfig = PlannerConfig()
    reflector: ReflectorConfig = ReflectorConfig()
    multi_step: MultiStepConfig = MultiStepConfig()
    proactive: ProactiveConfig = ProactiveConfig()
    system_control: SystemControlConfig = SystemControlConfig()
    web_automation: WebAutomationConfig = WebAutomationConfig()
```

- [ ] **Step 5: 运行测试确认通过**

Run: `python -m pytest tests/test_web_automation.py -v`
Expected: 2 passed

- [ ] **Step 6: 提交**

```bash
git add config/schema.py tests/test_web_automation.py
git commit -m "feat: 添加 WebAutomationConfig 配置"
```

---

## Task 2: 实现 browser.py

**Files:**
- Create: `plugins/web_automation/__init__.py`
- Create: `plugins/web_automation/browser.py`

- [ ] **Step 1: 写测试**

添加到 `tests/test_web_automation.py`：

```python
from unittest.mock import patch, MagicMock


@patch("plugins.web_automation.browser.sync_playwright")
def test_run_headless(mock_playwright_ctx):
    from plugins.web_automation.browser import run_headless

    mock_pw = MagicMock()
    mock_playwright_ctx.return_value.__enter__ = MagicMock(return_value=mock_pw)
    mock_playwright_ctx.return_value.__exit__ = MagicMock(return_value=False)
    mock_browser = MagicMock()
    mock_pw.chromium.launch.return_value = mock_browser
    mock_page = MagicMock()
    mock_browser.new_page.return_value = mock_page

    callback = MagicMock(return_value="test_result")
    result = run_headless(callback)

    mock_pw.chromium.launch.assert_called_once_with(channel="msedge", headless=True)
    callback.assert_called_once_with(mock_page)
    mock_browser.close.assert_called_once()
    assert result == "test_result"


@patch("plugins.web_automation.browser.sync_playwright")
def test_run_visible_does_not_close(mock_playwright_ctx):
    from plugins.web_automation.browser import run_visible

    mock_pw = MagicMock()
    mock_playwright_ctx.return_value.__enter__ = MagicMock(return_value=mock_pw)
    mock_playwright_ctx.return_value.__exit__ = MagicMock(return_value=False)
    mock_browser = MagicMock()
    mock_pw.chromium.launch.return_value = mock_browser
    mock_page = MagicMock()
    mock_browser.new_page.return_value = mock_page

    callback = MagicMock(return_value="visible_result")
    result = run_visible(callback)

    mock_pw.chromium.launch.assert_called_once_with(channel="msedge", headless=False)
    callback.assert_called_once_with(mock_page)
    mock_browser.close.assert_not_called()
    assert result == "visible_result"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_web_automation.py::test_run_headless -v`
Expected: FAIL（ModuleNotFoundError）

- [ ] **Step 3: 实现 browser.py**

创建 `plugins/web_automation/__init__.py`（空文件）。

创建 `plugins/web_automation/browser.py`：

```python
from __future__ import annotations

from typing import Any, Callable

from playwright.sync_api import sync_playwright, Page


def run_headless(callback: Callable[[Page], Any]) -> Any:
    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel="msedge", headless=True)
        try:
            page = browser.new_page()
            return callback(page)
        finally:
            browser.close()


def run_visible(callback: Callable[[Page], Any]) -> Any:
    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel="msedge", headless=False)
        page = browser.new_page()
        return callback(page)
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_web_automation.py -k "browser" -v`
Expected: 2 passed

- [ ] **Step 5: 提交**

```bash
git add plugins/web_automation/__init__.py plugins/web_automation/browser.py tests/test_web_automation.py
git commit -m "feat: 实现 web_automation browser.py 浏览器管理"
```

---

## Task 3: 实现 search.py

**Files:**
- Create: `plugins/web_automation/search.py`

- [ ] **Step 1: 写测试**

添加到 `tests/test_web_automation.py`：

```python
from plugins.web_automation.search import search_bing, search_google, format_results


def _make_mock_page_bing():
    mock_page = MagicMock()
    mock_item1 = MagicMock()
    mock_item1.query_selector.side_effect = lambda sel: {
        "h2 a": MagicMock(inner_text=MagicMock(return_value="标题1"), get_attribute=MagicMock(return_value="https://example.com/1")),
        ".b_caption p": MagicMock(inner_text=MagicMock(return_value="摘要1")),
    }.get(sel)
    mock_item2 = MagicMock()
    mock_item2.query_selector.side_effect = lambda sel: {
        "h2 a": MagicMock(inner_text=MagicMock(return_value="标题2"), get_attribute=MagicMock(return_value="https://example.com/2")),
        ".b_caption p": MagicMock(inner_text=MagicMock(return_value="摘要2")),
    }.get(sel)
    mock_page.query_selector_all.return_value = [mock_item1, mock_item2]
    return mock_page


def test_search_bing():
    mock_page = _make_mock_page_bing()
    results = search_bing(mock_page, "test query", count=5)
    mock_page.goto.assert_called_once()
    assert len(results) == 2
    assert results[0]["title"] == "标题1"
    assert results[0]["url"] == "https://example.com/1"


def test_format_results():
    results = [
        {"title": "标题1", "url": "https://a.com", "snippet": "摘要1"},
        {"title": "标题2", "url": "https://b.com", "snippet": "摘要2"},
    ]
    text = format_results(results)
    assert "1. 标题1" in text
    assert "https://a.com" in text
    assert "摘要1" in text
    assert "2. 标题2" in text
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_web_automation.py::test_search_bing -v`
Expected: FAIL（ModuleNotFoundError）

- [ ] **Step 3: 实现 search.py**

创建 `plugins/web_automation/search.py`：

```python
from __future__ import annotations

from typing import Any
from urllib.parse import quote_plus


def search_bing(page: Any, query: str, count: int = 5) -> list[dict[str, str]]:
    url = f"https://www.bing.com/search?q={quote_plus(query)}"
    page.goto(url, wait_until="domcontentloaded")
    page.wait_for_selector(".b_algo", timeout=10000)

    items = page.query_selector_all(".b_algo")
    results: list[dict[str, str]] = []
    for item in items[:count]:
        link_el = item.query_selector("h2 a")
        snippet_el = item.query_selector(".b_caption p")
        if link_el:
            title = link_el.inner_text()
            href = link_el.get_attribute("href") or ""
            snippet = snippet_el.inner_text() if snippet_el else ""
            results.append({"title": title, "url": href, "snippet": snippet})
    return results


def search_google(page: Any, query: str, count: int = 5) -> list[dict[str, str]]:
    url = f"https://www.google.com/search?q={quote_plus(query)}"
    page.goto(url, wait_until="domcontentloaded")
    page.wait_for_selector(".g", timeout=10000)

    items = page.query_selector_all(".g")
    results: list[dict[str, str]] = []
    for item in items[:count]:
        link_el = item.query_selector("a")
        title_el = item.query_selector("h3")
        snippet_el = item.query_selector("[data-sncf], .VwiC3b")
        if link_el and title_el:
            title = title_el.inner_text()
            href = link_el.get_attribute("href") or ""
            snippet = snippet_el.inner_text() if snippet_el else ""
            results.append({"title": title, "url": href, "snippet": snippet})
    return results


def format_results(results: list[dict[str, str]]) -> str:
    if not results:
        return "未找到搜索结果"
    lines: list[str] = []
    for i, r in enumerate(results, 1):
        lines.append(f"{i}. {r['title']}")
        lines.append(f"   {r['url']}")
        if r["snippet"]:
            lines.append(f"   {r['snippet']}")
        lines.append("")
    return "\n".join(lines).strip()
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_web_automation.py -k "search" -v`
Expected: passed

- [ ] **Step 5: 提交**

```bash
git add plugins/web_automation/search.py tests/test_web_automation.py
git commit -m "feat: 实现 web_automation search.py 搜索引擎"
```

---

## Task 4: 实现 page.py

**Files:**
- Create: `plugins/web_automation/page.py`

- [ ] **Step 1: 写测试**

添加到 `tests/test_web_automation.py`：

```python
from plugins.web_automation.page import extract_text, screenshot


def test_extract_text():
    mock_page = MagicMock()
    mock_page.evaluate.return_value = "这是页面正文内容，包含一些有用的信息。"
    result = extract_text(mock_page, "https://example.com", max_length=20)
    mock_page.goto.assert_called_once()
    assert len(result) <= 25  # 20 + 截断提示


def test_extract_text_long_truncated():
    mock_page = MagicMock()
    mock_page.evaluate.return_value = "x" * 5000
    result = extract_text(mock_page, "https://example.com", max_length=100)
    assert len(result) <= 120


@patch("plugins.web_automation.page.Path")
def test_screenshot(mock_path_cls):
    mock_page = MagicMock()
    mock_path = MagicMock()
    mock_path_cls.return_value = mock_path
    mock_path.parent.exists.return_value = True

    result = screenshot(mock_page, "https://example.com", "data/screenshots/test.png")
    mock_page.goto.assert_called_once()
    mock_page.screenshot.assert_called_once()
    assert "test.png" in result
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_web_automation.py::test_extract_text -v`
Expected: FAIL（ModuleNotFoundError）

- [ ] **Step 3: 实现 page.py**

创建 `plugins/web_automation/page.py`：

```python
from __future__ import annotations

from pathlib import Path
from typing import Any


_EXTRACT_JS = """
() => {
    const scripts = document.querySelectorAll('script, style, noscript');
    scripts.forEach(el => el.remove());
    return document.body ? document.body.innerText : '';
}
"""


def extract_text(page: Any, url: str, max_length: int = 2000) -> str:
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=15000)
        text = page.evaluate(_EXTRACT_JS)
        text = "\n".join(line.strip() for line in text.splitlines() if line.strip())
        if len(text) > max_length:
            text = text[:max_length] + "\n...(内容已截断)"
        return text if text else "页面无文本内容"
    except Exception as e:
        return f"提取页面文本失败：{e}"


def screenshot(page: Any, url: str, save_path: str) -> str:
    try:
        path = Path(save_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        page.goto(url, wait_until="domcontentloaded", timeout=15000)
        page.screenshot(path=str(path), full_page=True)
        return f"截图已保存：{save_path}"
    except Exception as e:
        return f"截图失败：{e}"
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_web_automation.py -k "page or extract or screenshot" -v`
Expected: passed

- [ ] **Step 5: 提交**

```bash
git add plugins/web_automation/page.py tests/test_web_automation.py
git commit -m "feat: 实现 web_automation page.py 文本提取和截图"
```

---

## Task 5: 实现 plugin.py

**Files:**
- Create: `plugins/web_automation/plugin.py`

- [ ] **Step 1: 写测试**

添加到 `tests/test_web_automation.py`：

```python
from plugins.web_automation.plugin import Plugin, PermissionLevel


def test_wa_permission_level_ordering():
    assert PermissionLevel.LOW.value < PermissionLevel.MEDIUM.value
    assert PermissionLevel.MEDIUM.value < PermissionLevel.HIGH.value


def test_wa_plugin_has_all_tools():
    plugin = Plugin()
    tool_names = [t.name for t in plugin.tools()]
    assert "web_search" in tool_names
    assert "web_search_visible" in tool_names
    assert "web_extract" in tool_names
    assert "web_screenshot" in tool_names


def test_wa_low_permission_blocks_extract():
    plugin = Plugin()
    plugin._permission_level = PermissionLevel.LOW
    result = plugin.call_tool("web_extract", {"url": "https://example.com"})
    assert "权限不足" in result


def test_wa_low_permission_blocks_screenshot():
    plugin = Plugin()
    plugin._permission_level = PermissionLevel.LOW
    result = plugin.call_tool("web_screenshot", {"url": "https://example.com"})
    assert "权限不足" in result


def test_wa_medium_permission_blocks_screenshot():
    plugin = Plugin()
    plugin._permission_level = PermissionLevel.MEDIUM
    result = plugin.call_tool("web_screenshot", {"url": "https://example.com"})
    assert "权限不足" in result


@patch("plugins.web_automation.plugin.run_headless")
def test_wa_low_permission_allows_search(mock_run):
    mock_run.return_value = "1. 结果标题\n   https://example.com\n   摘要"
    plugin = Plugin()
    plugin._permission_level = PermissionLevel.LOW
    result = plugin.call_tool("web_search", {"query": "test"})
    mock_run.assert_called_once()
    assert "结果" in result


@patch("plugins.web_automation.plugin.run_headless")
def test_wa_medium_permission_allows_extract(mock_run):
    mock_run.return_value = "页面文本内容"
    plugin = Plugin()
    plugin._permission_level = PermissionLevel.MEDIUM
    result = plugin.call_tool("web_extract", {"url": "https://example.com"})
    mock_run.assert_called_once()
    assert "页面文本" in result
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_web_automation.py::test_wa_plugin_has_all_tools -v`
Expected: FAIL（ModuleNotFoundError）

- [ ] **Step 3: 实现 plugin.py**

创建 `plugins/web_automation/plugin.py`：

```python
from __future__ import annotations

from enum import IntEnum
from pathlib import Path
from datetime import datetime

import yaml

from sdk.base import BasePlugin, tool
from plugins.web_automation.browser import run_headless, run_visible
from plugins.web_automation.search import search_bing, search_google, format_results
from plugins.web_automation.page import extract_text, screenshot


class PermissionLevel(IntEnum):
    LOW = 0
    MEDIUM = 1
    HIGH = 2


_LEVEL_NAMES = {"low": PermissionLevel.LOW, "medium": PermissionLevel.MEDIUM, "high": PermissionLevel.HIGH}


def _load_config() -> dict:
    config_path = Path(__file__).parent.parent.parent / "data" / "config" / "agent.yaml"
    if config_path.exists():
        data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        return data.get("web_automation", {})
    return {}


class Plugin(BasePlugin):
    name = "web_automation"
    description = "网页自动化：搜索、提取文本、截图"

    def __init__(self):
        super().__init__()
        config = _load_config()
        level_str = config.get("permission_level", "medium")
        self._permission_level = _LEVEL_NAMES.get(level_str, PermissionLevel.MEDIUM)
        self._default_engine = config.get("default_engine", "bing")
        self._screenshot_dir = config.get("screenshot_dir", "data/screenshots")

    def _check_permission(self, required: PermissionLevel) -> str | None:
        if self._permission_level >= required:
            return None
        current_name = self._permission_level.name.lower()
        required_name = required.name.lower()
        return f"权限不足：当前等级为 {current_name}，该操作需要 {required_name} 及以上"

    def _get_engine(self, engine: str) -> str:
        return engine if engine in ("bing", "google") else self._default_engine

    def _do_search(self, page, query: str, engine: str, count: int = 5) -> str:
        engine = self._get_engine(engine)
        if engine == "google":
            results = search_google(page, query, count)
        else:
            results = search_bing(page, query, count)
        return format_results(results)

    @tool(
        description="后台搜索关键词，返回结果摘要",
        params={"query": "搜索关键词", "engine": "搜索引擎：bing 或 google，留空用默认", "count": "返回结果数量，默认5"},
    )
    def web_search(self, query: str, engine: str = "", count: int = 5) -> str:
        denied = self._check_permission(PermissionLevel.LOW)
        if denied:
            return denied
        try:
            return run_headless(lambda page: self._do_search(page, query, engine, count))
        except Exception as e:
            return f"搜索失败：{e}"

    @tool(
        description="打开可见浏览器搜索，用户可看到操作过程",
        params={"query": "搜索关键词", "engine": "搜索引擎：bing 或 google，留空用默认"},
    )
    def web_search_visible(self, query: str, engine: str = "") -> str:
        denied = self._check_permission(PermissionLevel.LOW)
        if denied:
            return denied
        try:
            return run_visible(lambda page: self._do_search(page, query, engine))
        except Exception as e:
            return f"搜索失败：{e}"

    @tool(
        description="提取指定网页的文本内容",
        params={"url": "要提取的网页 URL", "max_length": "最大返回字符数，默认2000"},
    )
    def web_extract(self, url: str, max_length: int = 2000) -> str:
        denied = self._check_permission(PermissionLevel.MEDIUM)
        if denied:
            return denied
        try:
            return run_headless(lambda page: extract_text(page, url, max_length))
        except Exception as e:
            return f"提取失败：{e}"

    @tool(
        description="截图指定网页并保存到本地",
        params={"url": "要截图的网页 URL", "filename": "文件名，留空自动生成"},
    )
    def web_screenshot(self, url: str, filename: str = "") -> str:
        denied = self._check_permission(PermissionLevel.HIGH)
        if denied:
            return denied
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"screenshot_{timestamp}.png"
        save_path = str(Path(self._screenshot_dir) / filename)
        try:
            return run_headless(lambda page: screenshot(page, url, save_path))
        except Exception as e:
            return f"截图失败：{e}"
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_web_automation.py -v`
Expected: 全部通过

- [ ] **Step 5: 提交**

```bash
git add plugins/web_automation/plugin.py tests/test_web_automation.py
git commit -m "feat: 实现 web_automation plugin.py 入口和权限控制"
```

---

## Task 6: 文档和集成

**Files:**
- Create: `plugins/web_automation/README.md`
- Create: `docs/plugin-web-automation.md`
- Modify: `docs/architecture.md`
- Modify: `CLAUDE.md`

- [ ] **Step 1: 创建 README.md**

创建 `plugins/web_automation/README.md`：

```markdown
# web_automation

网页自动化插件，基于 Playwright + Edge。

## 依赖

pip install playwright
playwright install msedge

## 配置

data/config/agent.yaml:

web_automation:
  permission_level: medium
  default_engine: bing
  screenshot_dir: data/screenshots
```

- [ ] **Step 2: 创建 docs/plugin-web-automation.md**

（完整的中文插件说明文档，包含功能、配置、工具列表、使用示例）

- [ ] **Step 3: 更新 docs/architecture.md**

在 plugins 部分添加 web_automation 描述。

- [ ] **Step 4: 更新 CLAUDE.md**

在当前阶段中添加 web_automation 插件完成记录。

- [ ] **Step 5: 运行完整测试**

Run: `python -m pytest tests/ -q --ignore=tests/test_plugin_import.py --ignore=tests/test_settings_window.py --ignore=tests/test_proactive.py`
Expected: 全部通过

- [ ] **Step 6: 提交**

```bash
git add plugins/web_automation/README.md docs/plugin-web-automation.md docs/architecture.md CLAUDE.md
git commit -m "docs: 添加 web_automation 插件文档"
```

