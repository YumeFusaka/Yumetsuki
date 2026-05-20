from pathlib import Path
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QStackedWidget, QPushButton, QLabel,
)
from PySide6.QtCore import Qt
from config.manager import ConfigManager
from ui.settings.pages.api_page import APIPage
from ui.settings.pages.character_page import CharacterPage
from ui.settings.pages.plugin_page import PluginPage
from ui.settings.pages.system_page import SystemPage

WINDOW_STYLE = """
QMainWindow {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #fff5f7, stop:0.4 #ffe8ef, stop:0.7 #fce4f0, stop:1 #f8e8ff);
}
"""

NAV_STYLE = """
QPushButton {
    background: transparent;
    border: none;
    border-radius: 8px;
    padding: 12px 16px;
    text-align: left;
    color: #8c6b7a;
    font-size: 14px;
}
QPushButton:hover {
    background: rgba(255, 182, 193, 0.25);
    color: #6b3a5a;
}
QPushButton:checked {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 rgba(255, 154, 162, 0.3), stop:1 rgba(220, 160, 220, 0.25));
    color: #d4567a;
    font-weight: bold;
}
"""


class SettingsWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Yumetsuki - 设置中心")
        self.setMinimumSize(900, 600)
        self.resize(1050, 680)
        self.setStyleSheet(WINDOW_STYLE)

        self._config = ConfigManager()

        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Left nav
        nav = QWidget()
        nav.setFixedWidth(180)
        nav.setStyleSheet("""
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 rgba(255,240,245,0.95), stop:1 rgba(248,228,240,0.9));
            border-right: 1px solid rgba(220, 160, 180, 0.2);
        """)
        nav_layout = QVBoxLayout(nav)
        nav_layout.setContentsMargins(12, 20, 12, 12)
        nav_layout.setSpacing(4)

        logo = QLabel("🌸 设置中心")
        logo.setStyleSheet("color: #9b4d6a; font-size: 16px; font-weight: bold; padding: 8px 4px 20px 4px;")
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
        right.setStyleSheet("background: transparent;")
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
        bottom.setStyleSheet("""
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 rgba(255,240,245,0.9), stop:1 rgba(248,230,242,0.9));
            border-top: 1px solid rgba(220, 160, 180, 0.2);
        """)
        bottom_layout = QHBoxLayout(bottom)
        bottom_layout.setContentsMargins(20, 0, 20, 0)
        bottom_layout.addStretch()

        save_btn = QPushButton("保存配置")
        save_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #ff9aaa, stop:0.5 #e8a0c8, stop:1 #c8a0e8);
                border: none; border-radius: 8px;
                padding: 10px 32px; color: white;
                font-size: 14px; font-weight: bold;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #ffb0be, stop:0.5 #f0b0d8, stop:1 #d8b0f0);
            }
        """)
        save_btn.clicked.connect(self._save)
        bottom_layout.addWidget(save_btn)

        right_layout.addWidget(bottom)
        root.addWidget(right, 1)

        self._switch_page(0)

    def _switch_page(self, index: int):
        self._stack.setCurrentIndex(index)
        for i, btn in enumerate(self._nav_buttons):
            btn.setChecked(i == index)

    def _save(self):
        self._api_page.apply()
        self._system_page.apply()
        self._config.save()
