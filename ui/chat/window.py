from pathlib import Path
from html import escape
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QLabel, QPushButton, QMenu,
    QApplication, QSizePolicy,
)
from PySide6.QtCore import Qt, QThread, Signal, QPoint, QSize
from PySide6.QtGui import QPixmap, QCursor, QAction, QPainter, QColor, QPainterPath, QBrush
from ui.chat.sprite import SpriteManager
from core.mcp_host import MCPHost
from core.plugin_host import PluginHost
from llm.manager import LLMManager
from llm.text_processor import ProcessedText
from config.schema import LLMConfig
from core.character import load_character, build_system_prompt


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


class GlassPanel(QWidget):
    """Frosted glass panel drawn with rounded rect + semi-transparent fill."""
    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(0, 0, self.width(), self.height(), 14, 14)
        p.fillPath(path, QBrush(QColor(255, 245, 250, 190)))
        # Subtle border
        p.setPen(QColor(220, 160, 180, 80))
        p.drawPath(path)
        p.end()


class ConversationPane(QWidget):
    """Keeps speaker name and dialog body pinned to the top-left."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.name_label = QLabel("...", self)
        self.dialog_label = QLabel("...", self)
        self.name_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.dialog_label.setTextFormat(Qt.TextFormat.RichText)
        self.dialog_label.setWordWrap(True)
        self.dialog_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        name_h = 24
        gap = 8
        self.name_label.setGeometry(0, 0, self.width(), name_h)
        self.dialog_label.setGeometry(0, name_h + gap, self.width(), max(0, self.height() - name_h - gap))


class ChatWindow(QWidget):
    """Desktop pet style chat window — frameless, transparent, draggable."""

    BASE_WIDTH = 420
    BASE_HEIGHT = 600
    MIN_SCALE = 0.5
    MAX_SCALE = 2.0
    CHARACTER_NAME_COLOR = "#9b3060"
    USER_NAME_COLOR = "#5f6fb2"

    def __init__(
        self,
        config: LLMConfig,
        character_dir: Path | None = None,
        plugin_host: PluginHost | None = None,
        mcp_host: MCPHost | None = None,
    ):
        super().__init__()
        self._scale = 1.0
        self._drag_pos: QPoint | None = None
        self._char_dir = character_dir

        # Window flags: frameless, transparent, always on top
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

        self._setup_ui()

        # LLM
        self._llm = LLMManager(config, plugin_host=plugin_host, mcp_host=mcp_host)
        self._worker = None
        self._char_name = ""
        self._sprite_mgr = SpriteManager(self._sprite_label, character_dir)

        if character_dir:
            char = load_character(character_dir)
            self._char_name = char.name
            self._set_speaker_name(char.name)
            self._sprite_mgr.load_character(char, character_dir)
            self._llm.set_character(build_system_prompt(char))

        self._apply_scale()

    def _setup_ui(self):
        # Main layout — no margins, sprite fills window
        self._root_layout = QVBoxLayout(self)
        self._root_layout.setContentsMargins(0, 0, 0, 0)
        self._root_layout.setSpacing(0)

        # Sprite label — fills upper area
        self._sprite_label = QLabel()
        self._sprite_label.setAlignment(Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignHCenter)
        self._sprite_label.setStyleSheet("background: transparent;")
        self._sprite_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._root_layout.addWidget(self._sprite_label, 1)

        # Glass panel at bottom
        self._panel = GlassPanel(self)
        panel_layout = QVBoxLayout(self._panel)
        panel_layout.setContentsMargins(20, 16, 20, 16)
        panel_layout.setSpacing(9)

        self._conversation_pane = ConversationPane()
        self._name_label = self._conversation_pane.name_label
        self._dialog_box = self._conversation_pane.dialog_label
        self._name_label.setStyleSheet("""
            color: #9b3060; font-size: 17px; font-weight: bold;
            background: transparent;
        """)

        self._dialog_box.setStyleSheet("""
            color: #4a3040; font-size: 15px;
            padding: 2px 0 8px 0; background: transparent;
        """)
        self._conversation_pane.setMinimumHeight(96)
        panel_layout.addWidget(self._conversation_pane, 1)

        # Input row: [input] [mic] [send]
        input_row = QHBoxLayout()
        input_row.setSpacing(6)

        self._input = QLineEdit()
        self._input.setPlaceholderText("输入消息...")
        self._input.setStyleSheet("""
            QLineEdit {
                background: rgba(255, 255, 255, 0.7);
                border: 1px solid rgba(220, 160, 180, 0.35);
                border-radius: 8px; padding: 8px 12px;
                color: #4a3040; font-size: 13px;
            }
            QLineEdit:focus { border-color: #d4567a; }
        """)
        self._input.returnPressed.connect(self._on_send)
        input_row.addWidget(self._input)

        mic_btn = QPushButton("🎤")
        mic_btn.setFixedSize(34, 34)
        mic_btn.setStyleSheet(self._circle_btn_style())
        mic_btn.setToolTip("语音输入")
        input_row.addWidget(mic_btn)

        send_btn = QPushButton("➤")
        send_btn.setFixedSize(34, 34)
        send_btn.setStyleSheet(self._circle_btn_style("#ff9aaa", "#ffb0be"))
        send_btn.setToolTip("发送")
        send_btn.clicked.connect(self._on_send)
        input_row.addWidget(send_btn)

        panel_layout.addLayout(input_row)

    def _circle_btn_style(self, bg="rgba(255,255,255,0.7)", hover="rgba(255,200,210,0.6)"):
        return f"""
            QPushButton {{
                background: {bg}; border: 1px solid rgba(220,160,180,0.3);
                border-radius: 17px; color: #6b4a5a; font-size: 14px;
            }}
            QPushButton:hover {{ background: {hover}; }}
        """

    def _set_speaker_name(self, name: str, is_user: bool = False) -> None:
        color = self.USER_NAME_COLOR if is_user else self.CHARACTER_NAME_COLOR
        self._name_label.setText(name)
        self._name_label.setStyleSheet(f"""
            color: {color}; font-size: 17px; font-weight: bold;
            background: transparent;
        """)

    def _set_dialog_text(self, text: str) -> None:
        body = escape(text).replace("\n", "<br>")
        self._dialog_box.setText(
            f"<div style='line-height: 145%; color: #4a3040; font-size: 15px;'>{body}</div>"
        )

    def _apply_scale(self):
        w = int(self.BASE_WIDTH * self._scale)
        h = int(self.BASE_HEIGHT * self._scale)
        self.setFixedSize(w, h)
        # Position glass panel at bottom ~38% of window
        panel_h = int(h * 0.38)
        self._panel.setGeometry(10, h - panel_h - 6, w - 20, panel_h)
        self._reload_sprite()

    def _reload_sprite(self):
        """Reload sprite at current scale."""
        sprite_area_h = int(self.height() * 0.85)
        self._sprite_label.setFixedHeight(sprite_area_h)
        target_size = QSize(self.width(), sprite_area_h)
        self._sprite_mgr.reload(target_size)

    # --- Dragging ---
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.pos()
            event.accept()

    def mouseMoveEvent(self, event):
        if self._drag_pos and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        self._drag_pos = None

    # --- Scaling via scroll wheel ---
    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        if delta > 0:
            self._scale = min(self.MAX_SCALE, self._scale + 0.1)
        else:
            self._scale = max(self.MIN_SCALE, self._scale - 0.1)
        self._apply_scale()

    # --- Right-click context menu ---
    def _show_context_menu(self, pos):
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background: rgba(255,245,250,0.95); border: 1px solid rgba(220,160,180,0.3);
                border-radius: 8px; padding: 4px;
            }
            QMenu::item { padding: 8px 20px; color: #4a3040; border-radius: 4px; }
            QMenu::item:selected { background: rgba(255,154,162,0.25); color: #9b3060; }
        """)

        zoom_in = menu.addAction("🔍 放大")
        zoom_out = menu.addAction("🔎 缩小")
        zoom_reset = menu.addAction("↺ 重置大小")
        menu.addSeparator()

        self._topmost_action = menu.addAction("📌 取消置顶" if self._is_topmost() else "📌 置顶")
        menu.addSeparator()

        settings_action = menu.addAction("⚙ 打开设置")
        quit_action = menu.addAction("✕ 关闭")

        action = menu.exec(self.mapToGlobal(pos))
        if action == zoom_in:
            self._scale = min(self.MAX_SCALE, self._scale + 0.15)
            self._apply_scale()
        elif action == zoom_out:
            self._scale = max(self.MIN_SCALE, self._scale - 0.15)
            self._apply_scale()
        elif action == zoom_reset:
            self._scale = 1.0
            self._apply_scale()
        elif action == self._topmost_action:
            self._toggle_topmost()
        elif action == settings_action:
            self._open_settings()
        elif action == quit_action:
            self.close()

    def _is_topmost(self) -> bool:
        return bool(self.windowFlags() & Qt.WindowType.WindowStaysOnTopHint)

    def _toggle_topmost(self):
        flags = self.windowFlags()
        if flags & Qt.WindowType.WindowStaysOnTopHint:
            flags &= ~Qt.WindowType.WindowStaysOnTopHint
        else:
            flags |= Qt.WindowType.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        self.show()

    def _open_settings(self):
        from ui.settings.window import SettingsWindow
        self._settings = SettingsWindow()
        self._settings.show()

    # --- Chat logic ---
    def _on_send(self):
        text = self._input.text().strip()
        if not text or self._worker is not None:
            return
        self._input.clear()
        self._set_speaker_name("我", is_user=True)
        self._set_dialog_text(text)

        self._worker = LLMWorker(self._llm, text)
        self._worker.chunk_received.connect(self._on_chunk, Qt.ConnectionType.QueuedConnection)
        self._worker.finished_signal.connect(self._on_llm_done, Qt.ConnectionType.QueuedConnection)
        self._worker.start()

    def _on_chunk(self, result: ProcessedText):
        if self._name_label.text() == "我" and self._char_name:
            self._set_speaker_name(self._char_name)
        self._set_dialog_text(result.clean_text)
        if result.emotion:
            self._sprite_mgr.set_emotion(result.emotion)

    def _on_llm_done(self):
        self._worker = None
