from pathlib import Path
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QStackedWidget, QPushButton, QLabel, QSizePolicy,
)
from PySide6.QtCore import Qt
from config.manager import ConfigManager
from ui.settings.pages.api_page import APIPage
from ui.settings.pages.character_page import CharacterPage
from ui.settings.pages.plugin_page import PluginPage
from ui.settings.pages.system_page import SystemPage

NAV_STYLE = """
QPushButton {
    background: transparent;
    border: none;
    border-radius: 8px;
    padding: 12px 16px;
    text-align: left;
    color: #a0a0b0;
    font-size: 14px;
}
QPushButton:hover {
    background: rgba(255,255,255,0.05);
    color: #e8e8ed;
}
QPushButton:checked {
    background: rgba(102, 126, 234, 0.15);
    color: #667eea;
    font-weight: bold;
}
"""


class SettingsWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Yumetsuki - 设置中心")
        self.setMinimumSize(900, 600)
        self.resize(1050, 680)
        self.setStyleSheet("background-color: #0f0f14;")

        self._config = ConfigManager()

        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Left nav
        nav = QWidget()
        nav.setFixedWidth(180)
        nav.setStyleSheet("background: #12121a; border-right: 1px solid rgba(255,255,255,0.06);")
        nav_layout = QVBoxLayout(nav)
        nav_layout.setContentsMargins(12, 20, 12, 12)
        nav_layout.setSpacing(4)

        logo = QLabel("⚙  设置中心")
        logo.setStyleSheet("color: #e8e8ed; font-size: 16px; font-weight: bold; padding: 8px 4px 20px 4px;")
        nav_layout.addWidget(logo)

        self._nav_buttons: list[QPushButton] = []
        pages_info = [("🤖  API 设定", 0), ("👤  角色管理", 1), ("🧩  插件", 2), ("⚙  系统", 3)]
        for label, idx in pages_info:
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setStyleSheet(NAV_STYLE)
            btn.clicked.connect(lambda checked, i=idx: self._switch_page(i))
            nav_layout.addWidget(btn)
            self._nav_buttons.append(btn)

        nav_layout.addStretch()
        root.addWidget(nav)

        # Right content
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        self._stack = QStackedWidget()
        self._api_page = APIPage(self._config.api)
        self._stack.addWidget(self._api_page)

        characters_dir = Path(__file__).parent.parent.parent / "data" / "characters"
        self._char_page = CharacterPage(characters_dir)
        self._stack.addWidget(self._char_page)

        self._plugin_page = PluginPage()
        self._stack.addWidget(self._plugin_page)

        self._system_page = SystemPage(self._config.system)
        self._stack.addWidget(self._system_page)

        right_layout.addWidget(self._stack, 1)

        # Bottom bar
        bottom = QWidget()
        bottom.setFixedHeight(56)
        bottom.setStyleSheet("background: #12121a; border-top: 1px solid rgba(255,255,255,0.06);")
        bottom_layout = QHBoxLayout(bottom)
        bottom_layout.setContentsMargins(20, 0, 20, 0)
        bottom_layout.addStretch()

        save_btn = QPushButton("保存配置")
        save_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #667eea, stop:1 #764ba2);
                border: none; border-radius: 8px;
                padding: 10px 32px; color: white;
                font-size: 14px; font-weight: bold;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #7b93f5, stop:1 #8b5fbf);
            }
        """)
        save_btn.clicked.connect(self._save)
        bottom_layout.addWidget(save_btn)

        right_layout.addWidget(bottom)
        root.addWidget(right, 1)

        # Default to first page
        self._switch_page(0)

    def _switch_page(self, index: int):
        self._stack.setCurrentIndex(index)
        for i, btn in enumerate(self._nav_buttons):
            btn.setChecked(i == index)

    def _save(self):
        self._api_page.apply()
        self._system_page.apply()
        self._config.save()
