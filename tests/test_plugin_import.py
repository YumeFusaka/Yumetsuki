from pathlib import Path

from config.schema import MCPServerConfig
from ui.settings.pages.plugin_page import (
    _copy_plugin_dir,
    _remove_plugin_dir,
    _remove_mcp_server,
    _toggle_mcp_server_enabled,
)


def test_copy_plugin_dir_requires_plugin_py(tmp_path):
    src = tmp_path / "source"
    src.mkdir()
    dest_root = tmp_path / "plugins"

    result = _copy_plugin_dir(src, dest_root)

    assert result is None
    assert not dest_root.exists()


def test_copy_plugin_dir_copies_valid_plugin(tmp_path):
    src = tmp_path / "hello_plugin"
    src.mkdir()
    (src / "plugin.py").write_text("class Plugin: pass", encoding="utf-8")
    (src / "README.md").write_text("hello", encoding="utf-8")
    dest_root = tmp_path / "plugins"

    result = _copy_plugin_dir(src, dest_root)

    assert result == dest_root / "hello_plugin"
    assert (result / "plugin.py").exists()
    assert (result / "README.md").read_text(encoding="utf-8") == "hello"


def test_remove_plugin_dir_requires_existing_plugin_py(tmp_path):
    plugins_root = tmp_path / "plugins"
    plugin_dir = plugins_root / "demo"
    plugin_dir.mkdir(parents=True)

    assert _remove_plugin_dir(plugin_dir, plugins_root) is False


def test_remove_plugin_dir_removes_valid_plugin(tmp_path):
    plugins_root = tmp_path / "plugins"
    plugin_dir = plugins_root / "demo"
    plugin_dir.mkdir(parents=True)
    (plugin_dir / "plugin.py").write_text("class Plugin: pass", encoding="utf-8")

    assert _remove_plugin_dir(plugin_dir, plugins_root) is True
    assert not plugin_dir.exists()


def test_toggle_mcp_server_enabled_flips_state():
    servers = [MCPServerConfig(name="notes", enabled=True)]

    assert _toggle_mcp_server_enabled(servers, 0) is True
    assert servers[0].enabled is False


def test_remove_mcp_server_by_index():
    servers = [MCPServerConfig(name="a"), MCPServerConfig(name="b")]

    assert _remove_mcp_server(servers, 1) is True
    assert [server.name for server in servers] == ["a"]
