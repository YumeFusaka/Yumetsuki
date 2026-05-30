from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication
from PySide6.QtWidgets import QDialog
from PySide6.QtWidgets import QLabel
from PySide6.QtWidgets import QListWidgetItem
from PySide6.QtWidgets import QSizePolicy
from PySide6.QtWidgets import QSplitter
from PySide6.QtWidgets import QTextEdit

from config.schema import MCPServerConfig
from config.manager import ConfigManager
from core.plugin_host import PluginHost
from ui.settings.pages.character_page import CharacterPage
from ui.settings.pages.mcp_page import (
    MCPPage,
    MCPServerDialog,
    _remove_mcp_server,
    _toggle_mcp_server_enabled,
)
from ui.settings.pages.plugin_page import (
    PluginCatalogEntry,
    PluginCatalogEntryDialog,
    PluginCatalogSourceDialog,
    PluginPage,
    _copy_plugin_dir,
    _remove_plugin_dir,
)


def _app() -> QApplication:
    app = QApplication.instance()
    return app or QApplication([])


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


def test_copy_plugin_dir_rejects_existing_plugin_without_overwrite(tmp_path):
    src = tmp_path / "hello_plugin"
    src.mkdir()
    (src / "plugin.py").write_text("class Plugin: pass", encoding="utf-8")
    dest_root = tmp_path / "plugins"
    existing = dest_root / "hello_plugin"
    existing.mkdir(parents=True)
    (existing / "plugin.py").write_text("ORIGINAL = True", encoding="utf-8")

    result = _copy_plugin_dir(src, dest_root)

    assert result is None
    assert (existing / "plugin.py").read_text(encoding="utf-8") == "ORIGINAL = True"


def test_plugin_host_records_loaded_plugin_status(tmp_path):
    plugin_dir = tmp_path / "plugins" / "demo"
    plugin_dir.mkdir(parents=True)
    (plugin_dir / "plugin.py").write_text(
        """
from sdk.base import BasePlugin, tool

class Plugin(BasePlugin):
    name = "demo"
    description = "Demo plugin"

    @tool(description="Echo text")
    def echo(self, text: str) -> str:
        return text
""",
        encoding="utf-8",
    )

    host = PluginHost(tmp_path / "plugins")
    host.load()

    assert len(host.statuses) == 1
    status = host.statuses[0]
    assert status.name == "demo"
    assert status.loaded is True
    assert status.tools_count == 1
    assert status.description == "Demo plugin"
    assert status.message == "loaded"


def test_plugin_host_records_failed_plugin_status(tmp_path):
    plugin_dir = tmp_path / "plugins" / "broken"
    plugin_dir.mkdir(parents=True)
    (plugin_dir / "plugin.py").write_text("raise RuntimeError('boom')", encoding="utf-8")

    host = PluginHost(tmp_path / "plugins")
    host.load()

    assert host.statuses[0].name == "broken"
    assert host.statuses[0].loaded is False
    assert "boom" in host.statuses[0].message


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


def test_remove_plugin_dir_rejects_builtin_plugin(tmp_path):
    plugins_root = tmp_path / "plugins"
    plugin_dir = plugins_root / "system_control"
    plugin_dir.mkdir(parents=True)
    (plugin_dir / "plugin.py").write_text("class Plugin: pass", encoding="utf-8")

    assert _remove_plugin_dir(plugin_dir, plugins_root) is False
    assert plugin_dir.exists()


def test_toggle_mcp_server_enabled_flips_state():
    servers = [MCPServerConfig(name="notes", enabled=True)]

    assert _toggle_mcp_server_enabled(servers, 0) is True
    assert servers[0].enabled is False


def test_remove_mcp_server_by_index():
    servers = [MCPServerConfig(name="a"), MCPServerConfig(name="b")]

    assert _remove_mcp_server(servers, 1) is True
    assert [server.name for server in servers] == ["a"]


def test_mcp_server_dialog_exposes_timeout_and_retry_fields(tmp_path):
    _app()
    page = MCPPage(config=ConfigManager(config_dir=tmp_path))
    server = MCPServerConfig(
        name="slow-tools",
        transport="sse",
        url="http://127.0.0.1:8000/mcp",
        connect_timeout_seconds=3,
        request_timeout_seconds=7,
        retry_attempts=2,
    )
    dialog = MCPServerDialog(page, server)

    try:
        result = dialog.get_result()

        assert result.connect_timeout_seconds == 3
        assert result.request_timeout_seconds == 7
        assert result.retry_attempts == 2
    finally:
        dialog.close()
        page.close()


def test_mcp_server_edit_preserves_timeout_retry_and_enabled(tmp_path, monkeypatch):
    _app()
    config = ConfigManager(config_dir=tmp_path)
    original = MCPServerConfig(
        name="local",
        transport="stdio",
        command="python server.py",
        enabled=False,
        connect_timeout_seconds=4,
        request_timeout_seconds=9,
        retry_attempts=1,
    )
    config.mcp.servers = [original]
    page = MCPPage(config=config)
    item = QListWidgetItem("local [stdio] 未连接")
    item.setData(Qt.ItemDataRole.UserRole, {"kind": "mcp_status", "index": 0, "detail": "local"})
    page._list.clear()
    page._list.addItem(item)

    class _AcceptedDialog:
        def __init__(self, *_args, **_kwargs):
            pass

        def exec(self):
            return QDialog.DialogCode.Accepted

        def get_result(self):
            return MCPServerConfig(
                name="local-new",
                transport="stdio",
                command="python new_server.py",
                connect_timeout_seconds=4,
                request_timeout_seconds=9,
                retry_attempts=1,
            )

    try:
        page._list.setCurrentRow(0)
        monkeypatch.setattr("ui.settings.pages.mcp_page.MCPServerDialog", _AcceptedDialog)
        monkeypatch.setattr("ui.settings.pages.mcp_page.confirm_action", lambda *_args, **_kwargs: True)
        monkeypatch.setattr(page, "_refresh_mcp", lambda *_args, **_kwargs: None, raising=False)
        page._edit_selected_mcp()

        updated = config.mcp.servers[0]
        assert updated.name == "local-new"
        assert updated.enabled is False
        assert updated.connect_timeout_seconds == 4
        assert updated.request_timeout_seconds == 9
        assert updated.retry_attempts == 1
    finally:
        page.close()


def test_plugin_catalog_dialogs_use_sakura_light_style():
    _app()
    source_dialog = PluginCatalogSourceDialog()
    entry_dialog = PluginCatalogEntryDialog([
        PluginCatalogEntry(name="demo", description="Demo", source="E:/plugins/demo"),
    ])

    assert "background: #fff5f7" in source_dialog.styleSheet()
    assert "QComboBox::down-arrow" in entry_dialog.styleSheet()
    assert "background: #fff5f7" in entry_dialog.styleSheet()

    source_dialog.close()
    entry_dialog.close()


def test_plugin_page_dynamic_items_use_injected_system_font_tokens(tmp_path):
    _app()
    config = ConfigManager(config_dir=tmp_path)
    config.system.font_size = 24
    page = PluginPage(config=config)

    item = page._add_list_item("外部：demo 已加载")

    assert page._config is config
    assert page._list.property("settingsItemFontRole") == "small"
    assert item.font().pointSize() == 15

    page.close()


def test_plugin_page_layout_prioritizes_full_plugin_list(tmp_path):
    _app()
    config = ConfigManager(config_dir=tmp_path)
    page = PluginPage(config=config)

    try:
        splitter = page.findChild(QSplitter)
        detail = page._detail

        assert splitter is not None
        assert splitter.orientation() == Qt.Orientation.Horizontal
        assert splitter.count() == 2
        assert page._list.objectName() == "pluginList"
        assert page._list.minimumHeight() >= 360
        assert page._list.minimumWidth() >= 340
        assert page._list.uniformItemSizes()
        assert isinstance(detail, QTextEdit)
        assert detail.isReadOnly()
        assert detail.minimumHeight() == 132
        assert detail.maximumHeight() <= 170
        assert detail.sizePolicy().verticalPolicy() == QSizePolicy.Policy.Fixed
        for combo in (page._system_control_permission, page._web_automation_permission):
            assert [combo.itemText(i) for i in range(combo.count())] == ["low", "medium", "high"]
    finally:
        page.close()


def test_plugin_page_tooltips_use_sakura_light_style(tmp_path):
    _app()
    page = PluginPage(config=ConfigManager(config_dir=tmp_path))

    try:
        style = page.styleSheet()
        assert "QToolTip" in style
        assert "background: #fff0f3" in style
        assert "color: #4a3040" in style
    finally:
        page.close()


def test_mcp_page_dynamic_items_use_injected_system_font_tokens(tmp_path):
    _app()
    config = ConfigManager(config_dir=tmp_path)
    config.system.font_size = 24
    page = MCPPage(config=config)

    item = page._add_list_item("server [stdio] 已连接")

    assert page._config is config
    assert item.font().pointSize() == 16

    page.close()


def test_dynamic_plugin_and_mcp_dialogs_use_parent_system_font_tokens(tmp_path):
    _app()
    config = ConfigManager(config_dir=tmp_path)
    config.system.font_size = 24
    plugin_page = PluginPage(config=config)
    mcp_page = MCPPage(config=config)

    source_dialog = PluginCatalogSourceDialog(plugin_page)
    mcp_dialog = MCPServerDialog(mcp_page)

    try:
        assert source_dialog._system_config is config.system
        assert mcp_dialog._system_config is config.system
        source_labels = source_dialog.findChildren(QLabel)
        mcp_labels = mcp_dialog.findChildren(QLabel)
        assert any("font-size: 20px" in label.styleSheet() for label in source_labels)
        assert any("font-size: 20px" in label.styleSheet() for label in mcp_labels)
        assert any("font-size: 15px" in label.styleSheet() for label in mcp_labels)
        assert "font-size: 16px" in mcp_dialog.styleSheet()
        assert "background: #fff5f7" in source_dialog.styleSheet()
        assert "background: #fff5f7" in mcp_dialog.styleSheet()
    finally:
        source_dialog.close()
        mcp_dialog.close()
        plugin_page.close()
        mcp_page.close()


def test_character_page_dynamic_items_use_injected_system_font_tokens(tmp_path):
    _app()
    config = ConfigManager(config_dir=tmp_path / "config")
    config.system.font_size = 24
    characters_dir = tmp_path / "characters"
    char_dir = characters_dir / "demo"
    char_dir.mkdir(parents=True)
    (char_dir / "prompt.md").write_text("demo", encoding="utf-8")

    page = CharacterPage(characters_dir, config=config)

    try:
        assert page._config is config
        assert page._list.item(0).font().pointSize() == 16
    finally:
        page.close()


def test_character_page_refuses_to_delete_core_files(tmp_path, monkeypatch):
    _app()
    config = ConfigManager(config_dir=tmp_path / "config")
    characters_dir = tmp_path / "characters"
    char_dir = characters_dir / "demo"
    char_dir.mkdir(parents=True)
    core_file = char_dir / "prompt.md"
    core_file.write_text("core prompt", encoding="utf-8")

    page = CharacterPage(characters_dir, config=config)
    messages = []
    monkeypatch.setattr(
        "ui.settings.pages.character_page.show_feedback",
        lambda _parent, title, message, success=True: messages.append((title, message, success)),
    )
    monkeypatch.setattr(
        "ui.settings.pages.character_page.confirm_action",
        lambda *_args, **_kwargs: True,
    )

    try:
        page._list.setCurrentRow(0)
        page._current_file_path = core_file
        page._del_file()

        assert core_file.exists()
        assert core_file.read_text(encoding="utf-8") == "core prompt"
        assert any("核心文件" in message for _title, message, _success in messages)
    finally:
        page.close()
