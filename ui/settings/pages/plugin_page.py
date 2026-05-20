from pathlib import Path

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QListWidget, QHBoxLayout, QPushButton

from core.plugin_host import PluginHost


class PluginPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
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
        btn_row.addWidget(add_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

    def _refresh_plugins(self) -> None:
        self._list.clear()
        self._host.load()

        if not self._host.plugins and not self._host.errors:
            self._list.addItem("（暂无已配置的插件）")
            return

        for plugin in self._host.plugins:
            tools_count = len(plugin.tools())
            desc = f" — {plugin.description}" if plugin.description else ""
            self._list.addItem(f"已加载：{plugin.name}{desc}（{tools_count} 个工具）")

        for error in self._host.errors:
            self._list.addItem(f"加载失败：{error.plugin} — {error.message}")
