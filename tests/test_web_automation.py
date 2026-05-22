from unittest.mock import patch, MagicMock

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
