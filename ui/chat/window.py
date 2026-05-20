from pathlib import Path
from PySide6.QtWidgets import QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QLineEdit, QLabel, QPushButton
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QColor
from ui.chat.web_view import ChatWebView
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
        self.setMinimumSize(1000, 700)
        self.setStyleSheet("background-color: #0f0f14;")

        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Left: sprite area
        self._sprite_label = QLabel()
        self._sprite_label.setFixedWidth(350)
        self._sprite_label.setAlignment(Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignHCenter)
        self._sprite_label.setStyleSheet("background: transparent;")
        layout.addWidget(self._sprite_label)

        # Right: chat area
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        self._web_view = ChatWebView()
        right_layout.addWidget(self._web_view, 1)

        # Input bar
        input_bar = QWidget()
        input_bar.setStyleSheet("background-color: #1a1a24; border-top: 1px solid rgba(255,255,255,0.06);")
        input_layout = QHBoxLayout(input_bar)
        input_layout.setContentsMargins(16, 10, 16, 10)

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

        send_btn = QPushButton("发送")
        send_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #667eea, stop:1 #764ba2);
                border: none;
                border-radius: 20px;
                padding: 10px 24px;
                color: white;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #7b93f5, stop:1 #8b5fbf);
            }
        """)
        send_btn.clicked.connect(self._on_send)
        input_layout.addWidget(send_btn)

        right_layout.addWidget(input_bar)
        layout.addWidget(right, 1)

        # Initialize LLM and sprite
        self._sprite_mgr = SpriteManager(self._sprite_label)
        self._llm = LLMManager(config)
        self._worker: LLMWorker | None = None

        if character_dir and character_dir.is_dir():
            char = load_character(character_dir)
            self._sprite_mgr.load_character(char, character_dir)
            self._llm.set_character(build_system_prompt(char))

    def _on_send(self):
        text = self._input.text().strip()
        if not text or self._worker is not None:
            return
        self._input.clear()
        self._web_view.add_user_message(text)
        self._web_view.start_assistant_message()

        self._worker = LLMWorker(self._llm, text)
        self._worker.chunk_received.connect(self._on_chunk)
        self._worker.finished_signal.connect(self._on_llm_done)
        self._worker.start()

    def _on_chunk(self, result: ProcessedText):
        self._web_view.update_assistant_message(result.clean_text)
        if result.emotion:
            self._sprite_mgr.set_emotion(result.emotion)

    def _on_llm_done(self):
        self._worker = None
