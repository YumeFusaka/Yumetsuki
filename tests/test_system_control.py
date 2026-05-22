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


from plugins.system_control.command import do_run_command


@patch("plugins.system_control.command.subprocess.run")
def test_run_command_success(mock_run):
    mock_run.return_value = MagicMock(
        stdout="hello\n", stderr="", returncode=0
    )
    result = do_run_command("echo hello", timeout=30)
    assert "hello" in result
    mock_run.assert_called_once()


@patch("plugins.system_control.command.subprocess.run")
def test_run_command_timeout(mock_run):
    import subprocess as sp
    mock_run.side_effect = sp.TimeoutExpired(cmd="sleep 100", timeout=5)
    result = do_run_command("sleep 100", timeout=5)
    assert "超时" in result or "timeout" in result.lower()


@patch("plugins.system_control.command.subprocess.run")
def test_run_command_output_truncated(mock_run):
    long_output = "x" * 5000
    mock_run.return_value = MagicMock(
        stdout=long_output, stderr="", returncode=0
    )
    result = do_run_command("cat bigfile", timeout=30)
    assert len(result) <= 4200  # 4096 + some prefix text


from plugins.system_control.plugin import Plugin, PermissionLevel


def test_permission_level_ordering():
    assert PermissionLevel.LOW.value < PermissionLevel.MEDIUM.value
    assert PermissionLevel.MEDIUM.value < PermissionLevel.HIGH.value


def test_plugin_has_all_tools():
    plugin = Plugin()
    tool_names = [t.name for t in plugin.tools()]
    assert "open_application" in tool_names
    assert "open_browser" in tool_names
    assert "open_file_manager" in tool_names
    assert "open_file" in tool_names
    assert "open_url" in tool_names
    assert "run_command" in tool_names


@patch("plugins.system_control.open.subprocess.Popen")
@patch("plugins.system_control.open.shutil.which", return_value="/usr/bin/notepad")
def test_plugin_low_permission_allows_open_app(mock_which, mock_popen):
    plugin = Plugin()
    plugin._permission_level = PermissionLevel.LOW
    result = plugin.call_tool("open_application", {"name": "notepad"})
    assert "已打开" in result


def test_plugin_low_permission_blocks_open_file():
    plugin = Plugin()
    plugin._permission_level = PermissionLevel.LOW
    result = plugin.call_tool("open_file", {"path": "C:/test.txt"})
    assert "权限不足" in result


def test_plugin_low_permission_blocks_run_command():
    plugin = Plugin()
    plugin._permission_level = PermissionLevel.LOW
    result = plugin.call_tool("run_command", {"command": "echo hi"})
    assert "权限不足" in result


@patch("plugins.system_control.open.os.path.exists", return_value=True)
@patch("plugins.system_control.open.os.startfile")
def test_plugin_medium_permission_allows_open_file(mock_startfile, mock_exists):
    plugin = Plugin()
    plugin._permission_level = PermissionLevel.MEDIUM
    result = plugin.call_tool("open_file", {"path": "C:/test.txt"})
    assert "已打开" in result


def test_plugin_medium_permission_blocks_run_command():
    plugin = Plugin()
    plugin._permission_level = PermissionLevel.MEDIUM
    result = plugin.call_tool("run_command", {"command": "echo hi"})
    assert "权限不足" in result


@patch("plugins.system_control.command.subprocess.run")
def test_plugin_high_permission_allows_run_command(mock_run):
    mock_run.return_value = MagicMock(stdout="hi\n", stderr="", returncode=0)
    plugin = Plugin()
    plugin._permission_level = PermissionLevel.HIGH
    result = plugin.call_tool("run_command", {"command": "echo hi", "timeout": 30})
    assert "hi" in result
