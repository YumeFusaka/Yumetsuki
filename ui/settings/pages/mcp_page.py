from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from config.manager import ConfigManager
from config.schema import MCPServerConfig
from core.mcp_host import MCPHost
from ui.settings.feedback import confirm_action, show_feedback
from ui.theme import (
    SAKURA_COMBO_BOX_STYLE,
    apply_settings_fonts,
    apply_settings_item_font,
    set_settings_font_role,
    settings_page_title,
)


DIALOG_STYLE = """
QDialog {
    background: #fff5f7; color: #4a3040;
}
QLabel { color: #4a3040; font-size: 13px; }
QLineEdit {
    background: rgba(255,255,255,0.8);
    border: 1px solid rgba(220,160,180,0.3);
    border-radius: 6px; padding: 6px 10px;
    color: #4a3040; font-size: 13px;
}
QLineEdit:focus { border-color: #d4567a; }
QPushButton {
    background: rgba(255,200,210,0.4);
    border: 1px solid rgba(220,160,180,0.3);
    border-radius: 6px; padding: 6px 16px;
    color: #6b4a5a; font-size: 13px;
}
QPushButton:hover { background: rgba(255,154,162,0.4); }
""" + SAKURA_COMBO_BOX_STYLE

PAGE_STYLE = """
QLabel { color: #6b4a5a; font-size: 13px; }
QListWidget {
    background: rgba(255,255,255,0.5);
    border: 1px solid rgba(220, 160, 180, 0.25);
    border-radius: 8px; padding: 8px; color: #4a3040;
    outline: none;
}
QListWidget::item { padding: 10px 12px; border-radius: 6px; color: #5a3050; }
QListWidget::item:selected {
    background: rgba(255, 154, 162, 0.25);
    color: #9b3060; border: 1px solid #d4567a;
}
QListWidget::item:hover { background: rgba(255, 200, 210, 0.2); }
QListWidget:focus { border-color: #d4567a; }
QPushButton {
    background: rgba(255,255,255,0.5);
    border: 1px solid rgba(220, 160, 180, 0.3);
    border-radius: 6px; padding: 8px 16px;
    color: #6b4a5a; font-size: 13px;
}
QPushButton:hover { background: rgba(255, 200, 210, 0.4); }
""" + SAKURA_COMBO_BOX_STYLE


def _format_mcp_status_detail(status) -> str:
    state = "已连接" if status.connected else "未连接"
    tools = "、".join(status.tool_names or []) or "无"
    return "\n".join([
        f"名称：{status.server}",
        f"状态：{state}",
        f"传输：{status.transport}",
        f"工具数量：{status.tools_count}",
        f"工具：{tools}",
        f"错误类型：{status.error_type or '无'}",
        f"消息：{status.message or '无'}",
    ])


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
    def __init__(self, parent=None, server: MCPServerConfig | None = None):
        super().__init__(parent)
        self._system_config = _dialog_system_config(parent)
        self.setWindowTitle("编辑 MCP 服务器" if server else "添加 MCP 服务器")
        self.setStyleSheet(DIALOG_STYLE)
        self.setMinimumWidth(460)

        layout = QFormLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        title = QLabel("编辑 MCP 服务器" if server else "添加 MCP 服务器")
        set_settings_font_role(title, "title")
        title.setStyleSheet("font-size: 17px; font-weight: bold; color: #7a3a5a;")
        layout.addRow("", title)

        self._name = QLineEdit(server.name if server else "")
        self._name.setPlaceholderText("如 local-tools")
        layout.addRow("名称:", self._name)

        self._transport = QComboBox()
        self._transport.addItems(["stdio", "sse"])
        self._transport.setCurrentText(server.transport if server else "stdio")
        self._transport.currentTextChanged.connect(self._sync_fields)
        layout.addRow("传输:", self._transport)

        self._command = QLineEdit(server.command if server else "")
        self._command.setPlaceholderText("如 python path/to/server.py")
        layout.addRow("命令:", self._command)

        self._url = QLineEdit(server.url if server else "")
        self._url.setPlaceholderText("如 http://127.0.0.1:8000/sse")
        layout.addRow("SSE URL:", self._url)

        risk = QLabel("stdio 会启动本地进程；sse 会连接网络服务。请只添加可信 MCP。")
        set_settings_font_role(risk, "small")
        risk.setWordWrap(True)
        risk.setStyleSheet("color: #9b3060; font-size: 12px;")
        layout.addRow("风险:", risk)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)
        self._sync_fields()
        apply_settings_fonts(self, self._system_config)

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


class MCPPage(QWidget):
    def __init__(self, parent=None, config: ConfigManager | None = None):
        super().__init__(parent)
        self._config = config or ConfigManager()
        self._mcp_host = MCPHost(self._config.mcp.servers)
        self.setStyleSheet(PAGE_STYLE)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(14)

        title = settings_page_title(QLabel("MCP"))
        layout.addWidget(title)

        desc = QLabel("管理 MCP 服务器、连接诊断和 MCP 工具列表。插件管理已拆分到独立页面。")
        desc.setStyleSheet("color: #8c6b7a; font-size: 13px;")
        layout.addWidget(desc)

        top_row = QHBoxLayout()
        self._summary = QLabel("MCP 工具：0")
        self._summary.setStyleSheet("color: #6b4a5a; font-size: 12px; font-weight: bold;")
        top_row.addWidget(self._summary)
        top_row.addStretch()
        refresh_btn = QPushButton("↻ 刷新连接")
        refresh_btn.clicked.connect(lambda: self._refresh_mcp(notify=True))
        top_row.addWidget(refresh_btn)
        layout.addLayout(top_row)

        self._list = QListWidget()
        self._list.currentItemChanged.connect(self._sync_detail)
        layout.addWidget(self._list, 1)

        self._detail = QLabel("选择 MCP 服务器或工具查看诊断详情。")
        self._detail.setWordWrap(True)
        self._detail.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._detail.setStyleSheet("""
            QLabel {
                background: rgba(255,255,255,0.5);
                border: 1px solid rgba(220, 160, 180, 0.25);
                border-radius: 8px;
                padding: 10px 12px;
                color: #4a3040;
                font-size: 12px;
            }
        """)
        layout.addWidget(self._detail)

        btn_row = QHBoxLayout()
        add_btn = QPushButton("+ 添加服务器")
        add_btn.clicked.connect(self._add_mcp_server)
        btn_row.addWidget(add_btn)

        edit_btn = QPushButton("编辑所选")
        edit_btn.clicked.connect(self._edit_selected_mcp)
        btn_row.addWidget(edit_btn)

        toggle_btn = QPushButton("启用/停用所选")
        toggle_btn.clicked.connect(self._toggle_selected_mcp)
        btn_row.addWidget(toggle_btn)

        remove_btn = QPushButton("删除所选")
        remove_btn.clicked.connect(self._remove_selected_mcp)
        btn_row.addWidget(remove_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self._refresh_mcp()

    def _refresh_mcp(self, notify: bool = False) -> None:
        self._list.clear()
        self._mcp_host.close()
        self._mcp_host = MCPHost(self._config.mcp.servers)
        self._mcp_host.connect_all()
        total_tools = sum(status.tools_count for status in self._mcp_host.statuses if status.connected)
        enabled = sum(1 for server in self._config.mcp.servers if server.enabled)
        self._summary.setText(
            f"MCP 工具：{total_tools}  服务器 {len(self._config.mcp.servers)}  ·  启用 {enabled}"
        )
        self._detail.setText("选择 MCP 服务器或工具查看诊断详情。")

        if not self._config.mcp.servers:
            self._add_list_item("（暂无 MCP 服务器）")
            return

        for index, server in enumerate(self._config.mcp.servers):
            status = self._status_for_server(server.name)
            if status is not None:
                state = "已连接" if status.connected else "未连接"
                message = status.message or "无消息"
                text = f"{server.name} [{server.transport}] {state} · {status.tools_count} 个工具 — {message}"
                detail = _format_mcp_status_detail(status)
            else:
                state = "已启用" if server.enabled else "已停用"
                text = f"{server.name} [{server.transport}] {state}"
                detail = f"名称：{server.name}\n状态：{state}\n传输：{server.transport}"
            item = self._add_list_item(text)
            item.setData(Qt.ItemDataRole.UserRole, {
                "kind": "mcp_status",
                "index": index,
                "detail": detail,
            })
            if status and status.tool_names:
                for tool_name in status.tool_names:
                    tool_item = self._add_list_item(f"  • {server.name}__{tool_name}")
                    tool_item.setData(Qt.ItemDataRole.UserRole, {
                        "kind": "mcp_tool",
                        "index": index,
                        "detail": f"工具：{server.name}__{tool_name}\n来源：MCP\n服务器：{server.name}",
                    })
        if notify:
            show_feedback(self, "刷新成功", "MCP 连接和工具列表已刷新。")

    def _status_for_server(self, name: str):
        return next((status for status in self._mcp_host.statuses if status.server == name), None)

    def _add_mcp_server(self) -> None:
        dlg = MCPServerDialog(self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        server = dlg.get_result()
        if not self._validate_server(server):
            return
        if not confirm_action(self, "确认添加 MCP", self._risk_message(server)):
            return
        self._config.mcp.servers.append(server)
        self._config.save_mcp()
        self._refresh_mcp()
        show_feedback(self, "添加成功", f"MCP 服务器 '{server.name}' 已添加。")

    def _edit_selected_mcp(self) -> None:
        data = self._selected_data()
        if not data or data.get("kind") != "mcp_status":
            self._show_error("请选择一个 MCP 服务器条目。")
            return
        index = data["index"]
        dlg = MCPServerDialog(self, self._config.mcp.servers[index])
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        server = dlg.get_result()
        if not self._validate_server(server):
            return
        if not confirm_action(self, "确认保存 MCP", self._risk_message(server)):
            return
        server.enabled = self._config.mcp.servers[index].enabled
        self._config.mcp.servers[index] = server
        self._config.save_mcp()
        self._refresh_mcp()
        show_feedback(self, "保存成功", f"MCP 服务器 '{server.name}' 已更新。")

    def _toggle_selected_mcp(self) -> None:
        data = self._selected_data()
        if not data or data.get("kind") != "mcp_status":
            self._show_error("请选择一个 MCP 服务器条目。")
            return
        if _toggle_mcp_server_enabled(self._config.mcp.servers, data["index"]):
            server = self._config.mcp.servers[data["index"]]
            self._config.save_mcp()
            self._refresh_mcp()
            state = "启用" if server.enabled else "停用"
            show_feedback(self, "状态已更新", f"MCP 服务器 '{server.name}' 已{state}。")

    def _remove_selected_mcp(self) -> None:
        data = self._selected_data()
        if not data or data.get("kind") != "mcp_status":
            self._show_error("请选择一个 MCP 服务器条目。")
            return
        server_name = self._config.mcp.servers[data["index"]].name
        if not confirm_action(self, "确认删除", f"确定删除 MCP 服务器 '{server_name}' 吗？"):
            return
        if _remove_mcp_server(self._config.mcp.servers, data["index"]):
            self._config.save_mcp()
            self._refresh_mcp()
            show_feedback(self, "删除成功", f"MCP 服务器 '{server_name}' 已删除。")

    def _validate_server(self, server: MCPServerConfig) -> bool:
        if not server.name:
            self._show_error("名称不能为空。")
            return False
        if server.transport == "stdio" and not server.command:
            self._show_error("stdio MCP 服务器需要填写启动命令。")
            return False
        if server.transport == "sse" and not server.url:
            self._show_error("sse MCP 服务器需要填写 URL。")
            return False
        return True

    def _risk_message(self, server: MCPServerConfig) -> str:
        if server.transport == "stdio":
            return f"MCP 服务器 '{server.name}' 将启动本地进程：{server.command}。确定继续吗？"
        return f"MCP 服务器 '{server.name}' 将连接网络地址：{server.url}。确定继续吗？"

    def _selected_data(self) -> dict | None:
        item = self._list.currentItem()
        if not item:
            return None
        return item.data(Qt.ItemDataRole.UserRole)

    def _sync_detail(self) -> None:
        data = self._selected_data()
        if data and data.get("detail"):
            self._detail.setText(data["detail"])
        else:
            self._detail.setText("选择 MCP 服务器或工具查看诊断详情。")

    def _add_list_item(self, text: str):
        self._list.addItem(text)
        item = self._list.item(self._list.count() - 1)
        apply_settings_item_font(item, self._config.system)
        return item

    def _show_error(self, message: str) -> None:
        show_feedback(self, "操作失败", message, success=False)


def _dialog_system_config(parent):
    while parent is not None:
        config = getattr(parent, "_config", None)
        if config is not None and hasattr(config, "system"):
            return config.system
        parent = parent.parent()
    return ConfigManager().system
