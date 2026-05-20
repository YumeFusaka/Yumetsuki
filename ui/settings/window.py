from pathlib import Path
from PySide6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QPushButton
from config.manager import ConfigManager
from ui.settings.pages.api_page import APIPage
from ui.settings.pages.character_page import CharacterPage


class SettingsWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Yumetsuki - 设置")
        self.setMinimumSize(700, 500)

        self._config = ConfigManager()

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)

        self._tabs = QTabWidget()
        self._tabs.setStyleSheet("""
            QTabWidget::pane {
                border: none;
                background: #0f0f14;
            }
            QTabBar::tab {
                background: #1a1a24;
                color: #a0a0b0;
                padding: 10px 24px;
                border: none;
                border-bottom: 2px solid transparent;
            }
            QTabBar::tab:selected {
                color: #e8e8ed;
                border-bottom-color: #667eea;
            }
            QTabBar::tab:hover {
                color: #e8e8ed;
            }
        """)

        self._api_page = APIPage(self._config.api)
        self._tabs.addTab(self._api_page, "API 设定")

        characters_dir = Path(__file__).parent.parent.parent / "data" / "characters"
        self._char_page = CharacterPage(characters_dir)
        self._tabs.addTab(self._char_page, "角色管理")

        layout.addWidget(self._tabs)

        # Bottom bar with save button
        bottom = QWidget()
        bottom.setStyleSheet("background: #1a1a24; border-top: 1px solid rgba(255,255,255,0.06);")
        bottom_layout = QHBoxLayout(bottom)
        bottom_layout.setContentsMargins(16, 10, 16, 10)
        bottom_layout.addStretch()

        save_btn = QPushButton("保存")
        save_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #667eea, stop:1 #764ba2);
                border: none;
                border-radius: 8px;
                padding: 10px 32px;
                color: white;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #7b93f5, stop:1 #8b5fbf);
            }
        """)
        save_btn.clicked.connect(self._save)
        bottom_layout.addWidget(save_btn)

        layout.addWidget(bottom)

        self.setStyleSheet("background-color: #0f0f14;")

    def _save(self):
        self._api_page.apply()
        self._config.save()
