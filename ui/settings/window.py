from pathlib import Path
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QStackedWidget, QPushButton, QLabel,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor, QLinearGradient
from config.manager import ConfigManager
from ui.settings.pages.api_page import APIPage
from ui.settings.pages.character_page import CharacterPage
from ui.settings.pages.plugin_page import PluginPage
from ui.settings.pages.system_page import SystemPage
from ui.chat.window import ChatWindow

try:
    from ctypes import windll, c_int, byref, sizeof, Structure, POINTER
    class COLORREF(Structure):
        _fields_ = [("color", c_int)]

    def _set_title_bar_color(hwnd):
        # DWMWA_CAPTION_COLOR = 35
        color = c_int(0x00C8A0FF)  # BGR: pink #FFA0C8
        windll.dwmapi.DwmSetWindowAttribute(hwnd, 35, byref(color), sizeof(color))
        # DWMWA_TEXT_COLOR = 36
        text_color = c_int(0x00FFFFFF)  # white
        windll.dwmapi.DwmSetWindowAttribute(hwnd, 36, byref(text_color), sizeof(text_color))
except Exception:
    def _set_title_bar_color(hwnd):
        pass


def _create_sakura_icon() -> QIcon:
    px = QPixmap(32, 32)
    px.fill(QColor(0, 0, 0, 0))
    p = QPainter(px)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    grad = QLinearGradient(0, 0, 32, 32)
    grad.setColorAt(0, QColor(255, 154, 180))
    grad.setColorAt(1, QColor(230, 130, 180))
    p.setBrush(grad)
    p.setPen(Qt.PenStyle.NoPen)
    p.drawEllipse(4, 4, 12, 14)
    p.drawEllipse(16, 4, 12, 14)
    p.drawEllipse(8, 12, 14, 12)
    p.drawEllipse(10, 2, 12, 12)
    p.end()
    return QIcon(px)


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
    background: rgba(255, 182, 193, 0.2);
    color: #6b3a5a;
}
QPushButton:checked {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 rgba(255, 154, 162, 0.25), stop:1 rgba(220, 160, 220, 0.2));
    color: #d4567a;
    font-weight: bold;
}
"""

GLOBAL_SCROLLBAR = """
QScrollBar:vertical {
    background: rgba(255, 220, 230, 0.2);
    width: 8px; border-radius: 4px; margin: 0;
}
QScrollBar::handle:vertical {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #ffb0c8, stop:1 #dda0d8);
    border-radius: 4px; min-height: 30px;
}
QScrollBar::handle:vertical:hover { background: #ff9ab8; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
QScrollBar:horizontal {
    background: rgba(255, 220, 230, 0.2);
    height: 8px; border-radius: 4px; margin: 0;
}
QScrollBar::handle:horizontal {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #ffb0c8, stop:1 #dda0d8);
    border-radius: 4px; min-width: 30px;
}
QScrollBar::handle:horizontal:hover { background: #ff9ab8; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal { background: transparent; }
"""


class SettingsWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("  🌸  Yumetsuki 设置中心")
        self.setMinimumSize(950, 640)
        self.resize(1100, 720)
        self.setWindowIcon(_create_sakura_icon())
        self.setStyleSheet(f"""
            QMainWindow {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #fff5f7, stop:0.3 #ffebf2,
                    stop:0.7 #fae4f0, stop:1 #f5e1f8);
            }}
            {GLOBAL_SCROLLBAR}
        """)

        self._config = ConfigManager()

        central = QWidget()
        central.setStyleSheet("background: transparent;")
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Left nav
        nav = QWidget()
        nav.setFixedWidth(180)
        nav.setStyleSheet("""
            background: rgba(255, 245, 250, 0.6);
            border-right: 1px solid rgba(220, 160, 180, 0.15);
        """)
        nav_layout = QVBoxLayout(nav)
        nav_layout.setContentsMargins(12, 16, 12, 12)
        nav_layout.setSpacing(4)

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
        bottom.setFixedHeight(52)
        bottom.setStyleSheet("""
            background: rgba(255, 245, 250, 0.5);
            border-top: 1px solid rgba(220, 160, 180, 0.15);
        """)
        bottom_layout = QHBoxLayout(bottom)
        bottom_layout.setContentsMargins(20, 0, 20, 0)

        launch_btn = QPushButton("🚀 启动对话")
        launch_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #66bb6a, stop:1 #43a047);
                border: none; border-radius: 8px;
                padding: 10px 28px; color: white;
                font-size: 14px; font-weight: bold;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #81c784, stop:1 #66bb6a);
            }
        """)
        launch_btn.clicked.connect(self._launch_chat)
        bottom_layout.addWidget(launch_btn)
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

    def showEvent(self, event):
        super().showEvent(event)
        _set_title_bar_color(int(self.winId()))

    def _switch_page(self, index: int):
        self._stack.setCurrentIndex(index)
        for i, btn in enumerate(self._nav_buttons):
            btn.setChecked(i == index)

    def _save(self):
        self._api_page.apply()
        self._system_page.apply()
        self._config.save()

    def _launch_chat(self):
        self._save()
        # Find first character
        characters_dir = Path(__file__).parent.parent.parent / "data" / "characters"
        char_dir = None
        if characters_dir.is_dir():
            for d in characters_dir.iterdir():
                if d.is_dir() and (d / "prompt.md").exists():
                    char_dir = d
                    break
        self._chat_window = ChatWindow(self._config.api.llm, character_dir=char_dir)
        self._chat_window.show()
