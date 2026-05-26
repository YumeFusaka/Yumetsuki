from __future__ import annotations

from typing import Any, Callable

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


def run_headless(callback: Callable[..., Any]) -> Any:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel="msedge", headless=True)
        try:
            page = browser.new_page()
            return callback(page)
        finally:
            browser.close()


def run_visible(callback: Callable[..., Any]) -> Any:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel="msedge", headless=False)
        page = browser.new_page()
        return callback(page)
