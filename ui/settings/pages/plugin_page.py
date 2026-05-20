from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QListWidget, QHBoxLayout, QPushButton


class PluginPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(16)

        title = QLabel("插件 / MCP")
        title.setStyleSheet("font-size: 22px; font-weight: bold; color: #e8e8ed;")
        layout.addWidget(title)

        desc = QLabel("管理 MCP 服务器和插件扩展。连接外部工具到 LLM 对话中。")
        desc.setStyleSheet("color: #a0a0b0; font-size: 13px;")
        layout.addWidget(desc)

        self._list = QListWidget()
        self._list.setStyleSheet("""
            QListWidget {
                background: rgba(255,255,255,0.03);
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 8px; padding: 8px; color: #e8e8ed;
            }
            QListWidget::item { padding: 10px 12px; border-radius: 6px; }
            QListWidget::item:selected { background: rgba(102, 126, 234, 0.2); }
        """)
        self._list.addItem("（暂无已配置的插件）")
        layout.addWidget(self._list, 1)

        btn_row = QHBoxLayout()
        add_btn = QPushButton("+ 添加 MCP 服务器")
        add_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255,255,255,0.06); border: 1px solid rgba(255,255,255,0.1);
                border-radius: 6px; padding: 8px 16px; color: #e8e8ed; font-size: 13px;
            }
            QPushButton:hover { background: rgba(255,255,255,0.1); }
        """)
        btn_row.addWidget(add_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)
