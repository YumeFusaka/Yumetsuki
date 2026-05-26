from __future__ import annotations

from enum import IntEnum
from pathlib import Path
from datetime import datetime

import yaml

from sdk.base import BasePlugin, tool
from plugins.web_automation.browser import BrowserSessionController, run_headless, run_visible
from plugins.web_automation.search import search_bing, search_google, format_results
from plugins.web_automation.page import (
    click_selector,
    extract_current_text,
    extract_text,
    fill_selector,
    navigate_current,
    screenshot,
    wait_for_selector,
)


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
        self._browser_headless = bool(config.get("browser_headless", False))
        self._browser_timeout_ms = int(config.get("browser_timeout_ms", 15000))
        self._page_wait_timeout_ms = int(config.get("page_wait_timeout_ms", 10000))
        self._max_extract_length = int(config.get("max_extract_length", 4000))
        self._session = BrowserSessionController()

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
        description="后台静默搜索关键词并返回结果摘要文本（不打开任何窗口，用户看不到浏览器）。仅当用户只需要搜索结果文本、未要求看到浏览器时使用",
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
        description="启动 Playwright 控制的可见自动化浏览器窗口并执行搜索。它不复用系统默认浏览器当前窗口，仅当用户明确要求看到自动化搜索过程时使用",
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
