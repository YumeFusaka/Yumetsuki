from unittest.mock import MagicMock

from plugins.web_automation.browser import BrowserSessionController
from plugins.web_automation.page import (
    click_selector,
    extract_current_text,
    fill_selector,
    navigate_current,
    wait_for_selector,
)
from plugins.web_automation.plugin import Plugin
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
    page.evaluate.return_value = "第一行\n\n第二行很长"

    result = extract_current_text(page, max_length=4)

    assert result.ok is True
    assert "第一行" in result.text_preview
    assert "内容已截断" in result.text_preview


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


def test_web_session_tools_call_controller(monkeypatch):
    plugin = Plugin()
    calls = []

    class FakeSession:
        def open(self, **kwargs):
            calls.append(("open", kwargs))
            return "opened"

        def status(self):
            calls.append(("status", {}))
            return "status"

        def close(self):
            calls.append(("close", {}))
            return "closed"

    fake = FakeSession()
    monkeypatch.setattr(plugin, "_session", fake)

    assert plugin.call_tool("web_session_open", {"headless": True}) == "opened"
    assert plugin.call_tool("web_session_status", {}) == "status"
    assert plugin.call_tool("web_session_close", {}) == "closed"
    assert calls[0][0] == "open"
