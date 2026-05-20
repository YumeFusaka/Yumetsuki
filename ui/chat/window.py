from pathlib import Path
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLineEdit, QLabel, QPushButton, QGraphicsOpacityEffect,
)
from PySide6.QtCore import Qt, QThread, Signal, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QPixmap, QFont, QColor, QPalette
from ui.chat.sprite import SpriteManager
from llm.manager import LLMManager
from llm.text_processor import ProcessedText
from config.schema import LLMConfig
from core.character import Character, load_character, build_system_prompt


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
        self.setWindowTitle("Yumetsuki")
        self.setMinimumSize(900, 650)
        self.resize(1100, 750)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)

        central = QWidget()
        central.setStyleSheet("background: rgba(15, 15, 20, 0.85); border-radius: 12px;")
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Title bar (draggable)
        title_bar = QWidget()
        title_bar.setFixedHeight(36)
        title_bar.setStyleSheet("background: rgba(20, 20, 28, 0.95); border-top-left-radius: 12px; border-top-right-radius: 12px;")
        title_layout = QHBoxLayout(title_bar)
        title_layout.setContentsMargins(16, 0, 8, 0)
        title_label = QLabel("Yumetsuki")
        title_label.setStyleSheet("color: rgba(255,255,255,0.6); font-size: 12px;")
        title_layout.addWidget(title_label)
        title_layout.addStretch()
        close_btn = QPushButton("✕")
        close_btn.setFixedSize(28, 28)
        close_btn.setStyleSheet("QPushButton { background: transparent; color: rgba(255,255,255,0.5); border: none; font-size: 14px; } QPushButton:hover { color: #ff5f57; }")
        close_btn.clicked.connect(self.close)
        title_layout.addWidget(close_btn)
        main_layout.addWidget(title_bar)

        # Sprite area (center, takes most space)
        self._sprite_label = QLabel()
        self._sprite_label.setAlignment(Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignHCenter)
        self._sprite_label.setStyleSheet("background: transparent;")
        main_layout.addWidget(self._sprite_label, 1)

        # Character name label
        self._name_label = QLabel()
        self._name_label.setStyleSheet("""
            color: #a8d8ff;
            font-size: 16px;
            font-weight: bold;
            padding: 4px 20px;
            background: transparent;
        """)
        self._name_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        main_layout.addWidget(self._name_label)

        # Dialog box (semi-transparent, galgame style)
        self._dialog_box = QLabel()
        self._dialog_box.setWordWrap(True)
        self._dialog_box.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self._dialog_box.setMinimumHeight(120)
        self._dialog_box.setMaximumHeight(160)
        self._dialog_box.setStyleSheet("""
            QLabel {
                background: rgba(0, 0, 0, 0.55);
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 8px;
                padding: 16px 20px;
                color: #f0f0f5;
                font-size: 15px;
                line-height: 1.8;
                margin: 0px 12px;
            }
        """)
        self._dialog_box.setText("")
        main_layout.addWidget(self._dialog_box)

        # Input bar
        input_bar = QWidget()
        input_bar.setStyleSheet("background: rgba(18, 18, 26, 0.9); border-bottom-left-radius: 12px; border-bottom-right-radius: 12px;")
        input_layout = QHBoxLayout(input_bar)
        input_layout.setContentsMargins(16, 10, 16, 12)
        input_layout.setSpacing(10)

        # Mic button
        self._mic_btn = QPushButton("🎤")
        self._mic_btn.setFixedSize(40, 40)
        self._mic_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255,255,255,0.06);
                border: 1px solid rgba(255,255,255,0.1);
                border-radius: 20px;
                font-size: 16px;
            }
            QPushButton:hover {
                background: rgba(102, 126, 234, 0.2);
                border-color: #667eea;
            }
        """)
        input_layout.addWidget(self._mic_btn)

        self._input = QLineEdit()
        self._input.setPlaceholderText("输入消息...")
        self._input.setStyleSheet("""
            QLineEdit {
                background: rgba(255,255,255,0.05);
                border: 1px solid rgba(255,255,255,0.1);
                border-radius: 20px;
                padding: 10px 18px;
                color: #e8e8ed;
                font-size: 14px;
            }
            QLineEdit:focus {
                border-color: #667eea;
            }
        """)
        self._input.returnPressed.connect(self._on_send)
        input_layout.addWidget(self._input)

        send_btn = QPushButton("➤")
        send_btn.setFixedSize(40, 40)
        send_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #667eea, stop:1 #764ba2);
                border: none;
                border-radius: 20px;
                color: white;
                font-size: 16px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #7b93f5, stop:1 #8b5fbf);
            }
        """)
        send_btn.clicked.connect(self._on_send)
        input_layout.addWidget(send_btn)

        main_layout.addWidget(input_bar)

        # Initialize
        self._sprite_mgr = SpriteManager(self._sprite_label)
        self._llm = LLMManager(config)
        self._worker: LLMWorker | None = None
        self._char_name = ""

        if character_dir and character_dir.is_dir():
            char = load_character(character_dir)
            self._char_name = char.name
            self._name_label.setText(char.name)
            self._sprite_mgr.load_character(char, character_dir)
            self._llm.set_character(build_system_prompt(char))

        # For dragging frameless window
        self._drag_pos = None

    def _on_send(self):
        text = self._input.text().strip()
        if not text or self._worker is not None:
            return
        self._input.clear()
        self._dialog_box.setText("...")
        if self._char_name:
            self._name_label.setText(self._char_name)

        self._worker = LLMWorker(self._llm, text)
        self._worker.chunk_received.connect(self._on_chunk)
        self._worker.finished_signal.connect(self._on_llm_done)
        self._worker.start()

    def _on_chunk(self, result: ProcessedText):
        self._dialog_box.setText(result.clean_text)
        if result.emotion:
            self._sprite_mgr.set_emotion(result.emotion)

    def _on_llm_done(self):
        self._worker = None

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and event.position().y() < 36:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if self._drag_pos is not None:
            self.move(event.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, event):
        self._drag_pos = None
