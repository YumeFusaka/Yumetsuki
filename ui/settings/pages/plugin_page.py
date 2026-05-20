from pathlib import Path

from PySide6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout, QLabel,
    QLineEdit, QListWidget, QMessageBox, QPushButton, QVBoxLayout, QWidget,
)

from config.manager import ConfigManager
from config.schema import MCPServerConfig
from core.plugin_host import PluginHost


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
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(16)

        title = QLabel("插件 / MCP")
        title.setStyleSheet("font-size: 22px; font-weight: bold; color: #7a3a5a;")
        layout.addWidget(title)

        desc = QLabel("管理 MCP 服务器和插件扩展。连接外部工具到 LLM 对话中。")
        desc.setStyleSheet("color: #8c6b7a; font-size: 13px;")
        layout.addWidget(desc)

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
        btn_row.addStretch()
        layout.addLayout(btn_row)

    def _refresh_plugins(self) -> None:
        self._list.clear()
        self._host.load()

        if not self._host.plugins and not self._host.errors and not self._config.mcp.servers:
            self._list.addItem("（暂无已配置的插件）")
            return

        for plugin in self._host.plugins:
            tools_count = len(plugin.tools())
            desc = f" — {plugin.description}" if plugin.description else ""
            self._list.addItem(f"已加载：{plugin.name}{desc}（{tools_count} 个工具）")

        for error in self._host.errors:
            self._list.addItem(f"加载失败：{error.plugin} — {error.message}")

        for server in self._config.mcp.servers:
            status = "启用" if server.enabled else "停用"
            target = server.url if server.transport == "sse" else server.command
            self._list.addItem(f"MCP：{server.name} [{server.transport}] {target}（{status}）")

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

    def _show_error(self, message: str) -> None:
        dlg = QMessageBox(self)
        dlg.setStyleSheet(DIALOG_STYLE)
        dlg.setWindowTitle("添加失败")
        dlg.setText(message)
        dlg.exec()
