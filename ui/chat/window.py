from pathlib import Path
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLineEdit, QLabel, QPushButton,
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QPixmap, QIcon, QPainter, QColor, QLinearGradient
from ui.chat.sprite import SpriteManager
from llm.manager import LLMManager
from llm.text_processor import ProcessedText
from config.schema import LLMConfig
from core.character import Character, load_character, build_system_prompt

try:
    from ctypes import windll, c_int, byref, sizeof
    def _set_title_bar_color(hwnd):
        color = c_int(0x00C8A0FF)  # BGR pink
        windll.dwmapi.DwmSetWindowAttribute(hwnd, 35, byref(color), sizeof(color))
        text_color = c_int(0x00FFFFFF)
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


class LLMWorker(QThread):
    chunk_received = Signal(object)
    finished_signal = Signal()

    def __init__(self, llm: LLMManager, user_input: str):
        super().__init__()
        self._llm = llm
        self._input = user_input

    def run(self):
        for result in self._llm.chat_stream(self._input):
            self.chunk_received.emit(result)
        self.finished_signal.emit()


class ChatWindow(QMainWindow):
    def __init__(self, config: LLMConfig, character_dir: Path | None = None):
        super().__init__()
        self.setWindowTitle("  🌸  Yumetsuki")
        self.setMinimumSize(900, 650)
        self.resize(1100, 750)
        self.setWindowIcon(_create_sakura_icon())
        self.setStyleSheet("""
            QMainWindow {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #fff5f7, stop:0.3 #ffebf2,
                    stop:0.7 #fae4f0, stop:1 #f5e1f8);
            }
            QScrollBar:vertical {
                background: rgba(255, 220, 230, 0.2);
                width: 8px; border-radius: 4px;
            }
            QScrollBar::handle:vertical {
                background: #ffb0c8; border-radius: 4px; min-height: 30px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
        """)

        central = QWidget()
        central.setStyleSheet("background: transparent;")
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Sprite area — aligned to bottom
        self._sprite_label = QLabel()
        self._sprite_label.setAlignment(Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignHCenter)
        self._sprite_label.setStyleSheet("background: transparent;")
        main_layout.addWidget(self._sprite_label, 1)

        # Dialog area (overlaps bottom of sprite)
        dialog_area = QWidget()
        dialog_area.setStyleSheet("""
            background: rgba(255, 245, 250, 0.85);
            border-top: 1px solid rgba(220, 160, 180, 0.3);
        """)
        dialog_layout = QVBoxLayout(dialog_area)
        dialog_layout.setContentsMargins(24, 12, 24, 16)
        dialog_layout.setSpacing(8)

        # Character name
        self._name_label = QLabel("...")
        self._name_label.setStyleSheet("""
            color: #9b4d6a; font-size: 15px; font-weight: bold;
            background: transparent;
        """)
        dialog_layout.addWidget(self._name_label)

        # Dialog text
        self._dialog_box = QLabel("...")
        self._dialog_box.setWordWrap(True)
        self._dialog_box.setStyleSheet("""
            color: #4a3040; font-size: 14px; line-height: 1.6;
            padding: 8px 4px; background: transparent;
        """)
        self._dialog_box.setMinimumHeight(60)
        dialog_layout.addWidget(self._dialog_box)

        # Input row
        input_row = QHBoxLayout()
        input_row.setSpacing(10)

        self._input = QLineEdit()
        self._input.setPlaceholderText("输入消息...")
        self._input.setStyleSheet("""
            QLineEdit {
                background: rgba(255, 255, 255, 0.7);
                border: 1px solid rgba(220, 160, 180, 0.3);
                border-radius: 8px; padding: 10px 16px;
                color: #4a3040; font-size: 14px;
            }
            QLineEdit:focus { border-color: #d4567a; }
        """)
        self._input.returnPressed.connect(self._on_send)
        input_row.addWidget(self._input)

        send_btn = QPushButton("发送")
        send_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #ff9aaa, stop:1 #e8a0c8);
                border: none; border-radius: 8px;
                padding: 10px 24px; color: white;
                font-size: 14px; font-weight: bold;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #ffb0be, stop:1 #f0b0d8);
            }
        """)
        send_btn.clicked.connect(self._on_send)
        input_row.addWidget(send_btn)

        dialog_layout.addLayout(input_row)
        main_layout.addWidget(dialog_area)

        # LLM setup
        self._llm = LLMManager(config)
        self._worker = None
        self._char_name = ""
        self._sprite_mgr = SpriteManager(self._sprite_label, character_dir)

        if character_dir:
            char = load_character(character_dir)
            self._char_name = char.name
            self._name_label.setText(char.name)
            self._sprite_mgr.load_character(char, character_dir)
            self._llm.set_character(build_system_prompt(char))

    def showEvent(self, event):
        super().showEvent(event)
        _set_title_bar_color(int(self.winId()))

    def _on_send(self):
        text = self._input.text().strip()
        if not text or self._worker is not None:
            return
        self._input.clear()
        # Show user message first
        self._name_label.setText("我")
        self._dialog_box.setText(text)

        self._worker = LLMWorker(self._llm, text)
        self._worker.chunk_received.connect(self._on_chunk, Qt.ConnectionType.QueuedConnection)
        self._worker.finished_signal.connect(self._on_llm_done, Qt.ConnectionType.QueuedConnection)
        self._worker.start()

    def _on_chunk(self, result: ProcessedText):
        # Switch to character name on first chunk
        if self._name_label.text() == "我" and self._char_name:
            self._name_label.setText(self._char_name)
        self._dialog_box.setText(result.clean_text)
        if result.emotion:
            self._sprite_mgr.set_emotion(result.emotion)

    def _on_llm_done(self):
        self._worker = None
