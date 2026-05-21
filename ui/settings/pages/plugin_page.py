from pathlib import Path
import shutil

from PySide6.QtWidgets import (
    QFileDialog, QComboBox, QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout, QLabel,
    QLineEdit, QListWidget, QPushButton, QVBoxLayout, QWidget,
)
from PySide6.QtCore import Qt

from config.manager import ConfigManager
from config.schema import MCPServerConfig
from core.mcp_host import MCPHost
from core.plugin_host import PluginHost
from core.tool_registry import ToolRegistry
from ui.settings.feedback import confirm_action, show_feedback


DIALOG_STYLE = """
QDialog {
    background: #fff5f7; color: #4a3040;
}
QLabel { color: #4a3040; font-size: 13px; }
QLineEdit, QComboBox {
    background: rgba(255,255,255,0.8);
    border: 1px solid rgba(220,160,180,0.3);
    border-radius: 6px; padding: 6px 10px;
    color: #4a3040; font-size: 13px;
}
QLineEdit:focus, QComboBox:focus { border-color: #d4567a; }
QPushButton {
    background: rgba(255,200,210,0.4);
    border: 1px solid rgba(220,160,180,0.3);
    border-radius: 6px; padding: 6px 16px;
    color: #6b4a5a; font-size: 13px;
}
QPushButton:hover { background: rgba(255,154,162,0.4); }
QComboBox::drop-down { border: none; }
QComboBox QAbstractItemView {
    background: #fff5f7; color: #4a3040;
    selection-background-color: rgba(255,154,162,0.3);
}
"""


def _copy_plugin_dir(src: Path, dest_root: Path) -> Path | None:
    if not src.is_dir() or not (src / "plugin.py").exists():
        return None
    dest_root.mkdir(parents=True, exist_ok=True)
    dest = dest_root / src.name
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(src, dest)
    return dest


def _remove_plugin_dir(plugin_dir: Path, dest_root: Path) -> bool:
    try:
        plugin_dir.relative_to(dest_root)
    except ValueError:
        return False
    if not plugin_dir.is_dir() or not (plugin_dir / "plugin.py").exists():
        return False
    shutil.rmtree(plugin_dir)
    return True


def _toggle_mcp_server_enabled(servers: list[MCPServerConfig], index: int) -> bool:
    if index < 0 or index >= len(servers):
        return False
    servers[index].enabled = not servers[index].enabled
    return True


def _remove_mcp_server(servers: list[MCPServerConfig], index: int) -> bool:
    if index < 0 or index >= len(servers):
        return False
    del servers[index]
    return True


class MCPServerDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("添加 MCP 服务器")
        self.setStyleSheet(DIALOG_STYLE)
        self.setMinimumWidth(420)

        layout = QFormLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        self._name = QLineEdit()
        self._name.setPlaceholderText("如 local-tools")
        layout.addRow("名称:", self._name)

        self._transport = QComboBox()
        self._transport.addItems(["stdio", "sse"])
        self._transport.currentTextChanged.connect(self._sync_fields)
        layout.addRow("传输:", self._transport)

        self._command = QLineEdit()
        self._command.setPlaceholderText("如 python path/to/server.py")
        layout.addRow("命令:", self._command)

        self._url = QLineEdit()
        self._url.setPlaceholderText("如 http://127.0.0.1:8000/sse")
        layout.addRow("SSE URL:", self._url)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)
        self._sync_fields()

    def _sync_fields(self) -> None:
        is_sse = self._transport.currentText() == "sse"
        self._command.setEnabled(not is_sse)
        self._url.setEnabled(is_sse)

    def get_result(self) -> MCPServerConfig:
        return MCPServerConfig(
            name=self._name.text().strip(),
            transport=self._transport.currentText(),
            command=self._command.text().strip(),
            url=self._url.text().strip(),
        )


class PluginPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._config = ConfigManager()
        self._mcp_host = MCPHost(self._config.mcp.servers)
        self._tool_registry = ToolRegistry()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(16)

        title = QLabel("插件 / MCP")
        title.setStyleSheet("font-size: 22px; font-weight: bold; color: #7a3a5a;")
        layout.addWidget(title)

        desc = QLabel("管理 MCP 服务器和插件扩展。连接外部工具到 LLM 对话中。")
        desc.setStyleSheet("color: #8c6b7a; font-size: 13px;")
        layout.addWidget(desc)

        top_row = QHBoxLayout()
        self._summary = QLabel("工具目录：0")
        self._summary.setStyleSheet("color: #6b4a5a; font-size: 12px; font-weight: bold;")
        top_row.addWidget(self._summary)
        top_row.addStretch()
        refresh_btn = QPushButton("↻ 刷新工具目录")
        refresh_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255,255,255,0.5); border: 1px solid rgba(220, 160, 180, 0.3);
                border-radius: 6px; padding: 8px 16px; color: #6b4a5a; font-size: 13px;
            }
            QPushButton:hover { background: rgba(255, 200, 210, 0.4); }
        """)
        refresh_btn.clicked.connect(lambda: self._refresh_plugins(notify=True))
        top_row.addWidget(refresh_btn)
        layout.addLayout(top_row)

        self._list = QListWidget()
        self._list.setStyleSheet("""
            QListWidget {
                background: rgba(255,255,255,0.5);
                border: 1px solid rgba(220, 160, 180, 0.25);
                border-radius: 8px; padding: 8px; color: #4a3040;
                outline: none;
            }
            QListWidget::item { padding: 10px 12px; border-radius: 6px; color: #5a3050; }
            QListWidget::item:selected { background: rgba(255, 154, 162, 0.25); color: #9b3060; border: 1px solid #d4567a; }
            QListWidget::item:hover { background: rgba(255, 200, 210, 0.2); }
            QListWidget:focus { border-color: #d4567a; }
        """)
        self._host = PluginHost(Path(__file__).parent.parent.parent.parent / "plugins")
        self._refresh_plugins()
        layout.addWidget(self._list, 1)

        btn_row = QHBoxLayout()
        add_plugin_btn = QPushButton("+ 导入插件")
        add_plugin_btn.setToolTip("导入包含 plugin.py 的本地插件目录")
        add_plugin_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255,255,255,0.5); border: 1px solid rgba(220, 160, 180, 0.3);
                border-radius: 6px; padding: 8px 16px; color: #6b4a5a; font-size: 13px;
            }
            QPushButton:hover { background: rgba(255, 200, 210, 0.4); }
        """)
        add_plugin_btn.clicked.connect(self._import_plugin_dir)
        btn_row.addWidget(add_plugin_btn)

        add_btn = QPushButton("+ 添加 MCP 服务器")
        add_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255,255,255,0.5); border: 1px solid rgba(220, 160, 180, 0.3);
                border-radius: 6px; padding: 8px 16px; color: #6b4a5a; font-size: 13px;
            }
            QPushButton:hover { background: rgba(255, 200, 210, 0.4); }
        """)
        add_btn.clicked.connect(self._add_mcp_server)
        btn_row.addWidget(add_btn)
        toggle_btn = QPushButton("启用/停用所选")
        toggle_btn.setStyleSheet(add_btn.styleSheet())
        toggle_btn.clicked.connect(self._toggle_selected_mcp)
        btn_row.addWidget(toggle_btn)

        remove_btn = QPushButton("删除所选")
        remove_btn.setStyleSheet(add_btn.styleSheet())
        remove_btn.clicked.connect(self._remove_selected_item)
        btn_row.addWidget(remove_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

    def _refresh_plugins(self, notify: bool = False) -> None:
        self._list.clear()
        self._host.load()
        self._mcp_host = MCPHost(self._config.mcp.servers)
        self._mcp_host.connect_all()
        self._tool_registry = ToolRegistry(plugin_host=self._host, mcp_host=self._mcp_host)
        counts = self._tool_registry.counts_by_source()
        self._summary.setText(
            f"工具目录：{len(self._tool_registry.entries())}  "
            f"插件 {counts.get('plugin', 0)}  ·  MCP {counts.get('mcp', 0)}"
        )

        if not self._tool_registry.tool_specs() and not self._host.errors and not self._mcp_host.statuses:
            self._list.addItem("（暂无已配置的插件）")
            return

        if any(entry.source == "plugin" for entry in self._tool_registry.entries()):
            header = self._add_list_item("【本地插件工具】")
            header.setFlags(header.flags() & ~Qt.ItemFlag.ItemIsSelectable)
        for plugin in self._host.plugins:
            tools_count = len(plugin.tools())
            desc = f" — {plugin.description}" if plugin.description else ""
            item = self._add_list_item(f"已加载：{plugin.name}{desc}（{tools_count} 个工具）")
            item.setData(Qt.ItemDataRole.UserRole, {
                "kind": "plugin",
                "path": str((self._host._plugins_dir / plugin.name).resolve()),
            })

        if any(entry.source == "mcp" for entry in self._tool_registry.entries()):
            header = self._add_list_item("【MCP 工具】")
            header.setFlags(header.flags() & ~Qt.ItemFlag.ItemIsSelectable)
        for error in self._host.errors:
            self._list.addItem(f"加载失败：{error.plugin} — {error.message}")

        for index, status in enumerate(self._mcp_host.statuses):
            state = "已连接" if status.connected else "未连接"
            extra = f" / {status.tools_count} 个工具" if status.connected else ""
            item = self._add_list_item(f"MCP：{status.server} [{status.transport}] {state}{extra} — {status.message}")
            item.setData(Qt.ItemDataRole.UserRole, {"kind": "mcp", "index": index})
        for entry in self._tool_registry.entries():
            self._list.addItem(
                f"  • {entry.qualified_name} [{entry.source}] — "
                f"{entry.schema.get('description', '')}｜参数：{entry.parameter_summary()}"
            )
        if notify:
            show_feedback(self, "刷新成功", "统一工具目录已刷新。")

    def _add_mcp_server(self) -> None:
        dlg = MCPServerDialog(self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        server = dlg.get_result()
        if not server.name:
            self._show_error("名称不能为空。")
            return
        if server.transport == "stdio" and not server.command:
            self._show_error("stdio MCP 服务器需要填写启动命令。")
            return
        if server.transport == "sse" and not server.url:
            self._show_error("sse MCP 服务器需要填写 URL。")
            return
        self._config.mcp.servers.append(server)
        self._config.save_mcp()
        self._refresh_plugins()
        show_feedback(self, "添加成功", f"MCP 服务器 '{server.name}' 已添加。")

    def _import_plugin_dir(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "选择插件目录")
        if not folder:
            return
        plugins_root = Path(__file__).parent.parent.parent.parent / "plugins"
        imported = _copy_plugin_dir(Path(folder), plugins_root)
        if not imported:
            self._show_error("所选目录中没有 plugin.py。")
            return
        self._refresh_plugins()
        show_feedback(self, "导入成功", f"插件 '{imported.name}' 已导入。")

    def _toggle_selected_mcp(self) -> None:
        data = self._selected_data()
        if not data or data.get("kind") != "mcp":
            self._show_error("请选择一个 MCP 服务器条目。")
            return
        if _toggle_mcp_server_enabled(self._config.mcp.servers, data["index"]):
            server = self._config.mcp.servers[data["index"]]
            self._config.save_mcp()
            self._refresh_plugins()
            state = "启用" if server.enabled else "停用"
            show_feedback(self, "状态已更新", f"MCP 服务器 '{server.name}' 已{state}。")

    def _remove_selected_item(self) -> None:
        data = self._selected_data()
        if not data:
            self._show_error("请先选择一个插件或 MCP 服务器。")
            return
        if data.get("kind") == "plugin":
            plugins_root = Path(__file__).parent.parent.parent.parent / "plugins"
            plugin_name = Path(data["path"]).name
            if not confirm_action(self, "确认删除", f"确定删除插件 '{plugin_name}' 吗？"):
                return
            if _remove_plugin_dir(Path(data["path"]), plugins_root):
                self._refresh_plugins()
                show_feedback(self, "删除成功", f"插件 '{plugin_name}' 已删除。")
                return
        if data.get("kind") == "mcp":
            server_name = self._config.mcp.servers[data["index"]].name
            if not confirm_action(self, "确认删除", f"确定删除 MCP 服务器 '{server_name}' 吗？"):
                return
            if _remove_mcp_server(self._config.mcp.servers, data["index"]):
                self._config.save_mcp()
                self._refresh_plugins()
                show_feedback(self, "删除成功", f"MCP 服务器 '{server_name}' 已删除。")
                return
        self._show_error("当前选择的条目不支持删除。")

    def _selected_data(self) -> dict | None:
        item = self._list.currentItem()
        if not item:
            return None
        return item.data(Qt.ItemDataRole.UserRole)

    def _add_list_item(self, text: str):
        item = self._list.item(self._list.count())
        self._list.addItem(text)
        return self._list.item(self._list.count() - 1)

    def _show_error(self, message: str) -> None:
        show_feedback(self, "操作失败", message, success=False)
