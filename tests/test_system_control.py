import pytest
from config.schema import AgentConfig, SystemControlConfig


def test_system_control_config_defaults():
    config = SystemControlConfig()
    assert config.permission_level == "low"


def test_system_control_config_in_agent_config():
    agent = AgentConfig()
    assert agent.system_control.permission_level == "low"


def test_system_control_config_accepts_valid_levels():
    for level in ("low", "medium", "high"):
        config = SystemControlConfig(permission_level=level)
        assert config.permission_level == level


from unittest.mock import patch, MagicMock
import sys

sys.path.insert(0, ".")
from plugins.system_control.open import (
    do_open_application,
    do_open_browser,
    do_open_file_manager,
    do_open_file,
    do_open_url,
)


@patch("plugins.system_control.open.subprocess.Popen")
def test_open_application_found(mock_popen):
    result = do_open_application("notepad")
    mock_popen.assert_called_once()
    assert "notepad" in result


@patch("plugins.system_control.open.shutil.which", return_value=None)
def test_open_application_not_found(mock_which):
    result = do_open_application("nonexistent_app_xyz")
    assert "找不到" in result or "not found" in result.lower()


@patch("plugins.system_control.open.webbrowser.open")
def test_open_browser(mock_open):
    result = do_open_browser()
    mock_open.assert_called_once()
    assert "浏览器" in result or "browser" in result.lower()


@patch("plugins.system_control.open.os.startfile")
def test_open_file_manager_default(mock_startfile):
    result = do_open_file_manager("")
    mock_startfile.assert_called_once()
    assert "文件管理器" in result or "file manager" in result.lower()


@patch("plugins.system_control.open.os.path.exists", return_value=True)
@patch("plugins.system_control.open.os.startfile")
def test_open_file(mock_startfile, mock_exists):
    result = do_open_file("C:/test.txt")
    mock_startfile.assert_called_once_with("C:/test.txt")
    assert "C:/test.txt" in result


@patch("plugins.system_control.open.webbrowser.open")
def test_open_url(mock_open):
    result = do_open_url("https://example.com")
    mock_open.assert_called_once_with("https://example.com")
    assert "https://example.com" in result
