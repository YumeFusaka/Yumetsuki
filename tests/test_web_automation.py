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


@patch("playwright.sync_api.sync_playwright")
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


@patch("playwright.sync_api.sync_playwright")
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


def test_format_results_empty():
    assert format_results([]) == "未找到搜索结果"


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
