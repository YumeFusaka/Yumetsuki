from pathlib import Path
import getpass
import re
import unicodedata
from html import escape
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QLabel, QPushButton, QMenu,
    QApplication, QSizePolicy, QScrollArea,
)
from PySide6.QtCore import Qt, QThread, Signal, QPoint, QSize, QBuffer, QByteArray, QIODevice
from PySide6.QtGui import QPixmap, QCursor, QAction, QPainter, QColor, QPainterPath, QBrush, QPen
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from ui.chat.sprite import SpriteManager
from core.tool_registry import ToolRegistry
from agent.manager import AgentManager
from llm.manager import LLMManager
from llm.text_processor import ProcessedText
from llm.adapter import LLMStreamChunk
from config.schema import LLMConfig, TTSConfig
from core.character import load_character, build_system_prompt
from tts.adapters.gptsovits import GPTSoVITSAdapter


SENTENCE_ENDINGS = "。！？；\n"


class LLMWorker(QThread):
    chunk_received = Signal(object)
    finished_signal = Signal()

    def __init__(self, chat_engine, user_input: str):
        super().__init__()
        self._chat_engine = chat_engine
        self._input = user_input

    def run(self):
        for result in self._chat_engine.chat_stream(self._input):
            self.chunk_received.emit(result)
        self.finished_signal.emit()


class TTSWorker(QThread):
    result_ready = Signal(int, int, object)

    def __init__(self, adapter, utterance_id: int, segment_id: int, text: str):
        super().__init__()
        self._adapter = adapter
        self._utterance_id = utterance_id
        self._segment_id = segment_id
        self._text = text

    def run(self):
        audio = None
        if self._adapter is not None:
            audio = self._adapter.synthesize(self._text)
        self.result_ready.emit(self._utterance_id, self._segment_id, audio)


class TTSTranslationWorker(QThread):
    result_ready = Signal(int, int, object)

    def __init__(self, translate_func, utterance_id: int, segment_id: int, text: str, target_lang: str):
        super().__init__()
        self._translate_func = translate_func
        self._utterance_id = utterance_id
        self._segment_id = segment_id
        self._text = text
        self._target_lang = target_lang

    def run(self):
        translated_text = None
        if self._translate_func is not None:
            translated_text = self._translate_func(self._text, self._target_lang)
        self.result_ready.emit(self._utterance_id, self._segment_id, translated_text)


class GlassPanel(QWidget):
    """Frosted glass panel drawn with rounded rect + semi-transparent fill."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self._border_width = 3
        self._border_color = "#d4567a"

    def set_border_style(self, width: int, color: str) -> None:
        self._border_width = width
        self._border_color = color
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        panel_rect = self.rect().adjusted(2, 2, -2, -2)

        panel_path = QPainterPath()
        panel_path.addRoundedRect(panel_rect, 16, 16)

        p.fillPath(panel_path, QBrush(QColor(255, 245, 250, 168)))
        p.setPen(QPen(QColor(self._border_color), self._border_width))
        p.drawPath(panel_path)
        p.end()


class ConversationPane(QWidget):
    """Keeps speaker name and scrollable dialog body."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.name_label = QLabel("...", self)
        self.name_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)

        self._scroll_area = QScrollArea(self)
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._scroll_area.setFrameShape(QScrollArea.Shape.NoFrame)
        self._scroll_area.setStyleSheet("""
            QScrollArea { background: transparent; border: none; }
            QScrollBar:vertical {
                width: 6px; background: transparent;
            }
            QScrollBar::handle:vertical {
                background: rgba(212, 86, 122, 0.4); border-radius: 3px; min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background: rgba(212, 86, 122, 0.6);
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: transparent;
            }
        """)

        self.dialog_label = QLabel("...")
        self.dialog_label.setTextFormat(Qt.TextFormat.RichText)
        self.dialog_label.setWordWrap(True)
        self.dialog_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.dialog_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.dialog_label.setStyleSheet("background: transparent;")
        self._scroll_area.setWidget(self.dialog_label)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        name_h = 24
        gap = 8
        self.name_label.setGeometry(0, 0, self.width(), name_h)
        self._scroll_area.setGeometry(0, name_h + gap, self.width(), max(0, self.height() - name_h - gap))

    def scroll_to_top(self):
        self._scroll_area.verticalScrollBar().setValue(0)


class ChatWindow(QWidget):
    """Desktop pet style chat window — frameless, transparent, draggable."""

    BASE_WIDTH = 500
    BASE_HEIGHT = 600
    MIN_SCALE = 0.5
    MAX_SCALE = 2.0
    BASE_FONT = 17
    BASE_NAME_FONT = 17
    BASE_INPUT_FONT = 13
    BASE_PADDING = 12
    BASE_RADIUS = 8
    BASE_BTN_SIZE = 34
    BASE_SCROLLBAR_WIDTH = 6
    CHARACTER_NAME_COLOR = "#9b3060"
    USER_NAME_COLOR = "#5f6fb2"

    def __init__(
        self,
        config: LLMConfig,
        character_dir: Path | None = None,
        tool_registry: ToolRegistry | None = None,
        memory_store = None,
        user_id: str | None = None,
        settings_window_factory=None,
        agent_config = None,
        tts_config: TTSConfig | None = None,
    ):
        super().__init__()
        self._scale = 1.0
        self._drag_pos: QPoint | None = None
        self._char_dir = character_dir
        self._settings_window_factory = settings_window_factory
        self._settings_window = None
        self._tts_adapter = self._create_tts_adapter(tts_config)
        self._tts_output_lang = self._normalize_tts_lang(tts_config.output_lang if tts_config else "")
        self._streamed_assistant_text = ""
        self._tts_pending_buffer = ""
        self._current_utterance_id = 0
        self._next_segment_id = 0
        self._next_play_id = 0
        self._segment_results: dict[tuple[int, int], bytes] = {}
        self._active_tts_workers = []
        self._active_translation_workers = []
        self._audio_output = None
        self._audio_player = None
        self._audio_buffer = None
        self._is_audio_playing = False
        self._pending_audio_queue: list[bytes] = []

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
        self._llm = LLMManager(config, tool_registry=tool_registry)
        self._chat_engine = AgentManager(
            llm_manager=self._llm,
            memory_store=memory_store,
            tool_registry=tool_registry,
            user_id=user_id or getpass.getuser(),
            agent_config=agent_config,
        )
        self._worker = None
        self._char_name = ""
        self._sprite_mgr = SpriteManager(self._sprite_label, character_dir)

        # 主动行为调度器
        self._proactive_scheduler = None
        if agent_config is not None and agent_config.proactive.enabled:
            from agent.proactive import ProactiveScheduler
            self._proactive_scheduler = ProactiveScheduler(
                config=agent_config.proactive,
                llm_helper=self._chat_engine._llm_helper,
                parent=self,
            )
            self._proactive_scheduler.proactive_message.connect(
                self._on_proactive_message,
                Qt.ConnectionType.QueuedConnection,
            )
            self._proactive_scheduler.start()

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
        panel_layout.setContentsMargins(18, 14, 18, 14)
        panel_layout.setSpacing(7)

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
                border: 3px solid #d4567a;
                border-radius: 8px; padding: 8px 12px;
                color: #4a3040; font-size: 13px;
            }
            QLineEdit:focus { border-color: #9b3060; }
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

    def _circle_btn_style(
        self,
        bg="rgba(255,255,255,0.68)",
        hover="rgba(255,214,224,0.82)",
        border="rgba(212, 86, 122, 0.32)",
    ):
        return f"""
            QPushButton {{
                background: {bg};
                border: 3px solid #d4567a;
                border-radius: 17px; color: #6b4a5a; font-size: 14px;
            }}
            QPushButton:hover {{
                background: {hover};
                border-color: #9b3060;
            }}
        """

    def _set_speaker_name(self, name: str, is_user: bool = False) -> None:
        color = self.USER_NAME_COLOR if is_user else self.CHARACTER_NAME_COLOR
        font = int(self.BASE_NAME_FONT * self._scale)
        self._name_label.setText(name)
        self._name_label.setStyleSheet(f"""
            color: {color}; font-size: {font}px; font-weight: bold;
            background: transparent;
        """)

    @staticmethod
    def _scaled_border_widths(scale: float) -> tuple[int, int]:
        panel_border = max(2, round(3 * scale))
        control_border = max(1, round(2 * scale))
        return panel_border, control_border

    @staticmethod
    def _normalize_dialog_text(text: str) -> str:
        normalized = text.strip()
        return re.sub(r"\n{3,}", "\n\n", normalized)

    @staticmethod
    def _build_dialog_html(
        text: str,
        font: int,
        line_height: int = 132,
        paragraph_gap: int = 4,
    ) -> str:
        normalized = ChatWindow._normalize_dialog_text(text)
        if not normalized:
            return (
                f"<div style='line-height: {line_height}%; color: #4a3040; "
                f"font-size: {font}px; margin:0;'></div>"
            )

        paragraphs = normalized.split("\n\n")
        html_parts = []
        for index, paragraph in enumerate(paragraphs):
            margin = "0" if index == len(paragraphs) - 1 else f"0 0 {paragraph_gap}px 0"
            body = escape(paragraph).replace("\n", "<br>")
            html_parts.append(f"<div style='margin:{margin};'>{body}</div>")

        return (
            f"<div style='line-height: {line_height}%; color: #4a3040; "
            f"font-size: {font}px;'>{''.join(html_parts)}</div>"
        )

    def _set_dialog_text(self, text: str) -> None:
        font = int(self.BASE_FONT * self._scale)
        paragraph_gap = max(2, int(4 * self._scale))
        html = self._build_dialog_html(
            text,
            font=font,
            line_height=132,
            paragraph_gap=paragraph_gap,
        )
        self._dialog_box.setText(html)
        self._conversation_pane.scroll_to_top()

    def _apply_scale(self):
        w = int(self.BASE_WIDTH * self._scale)
        h = int(self.BASE_HEIGHT * self._scale)
        self.setFixedSize(w, h)
        panel_h = int(h * 0.45)
        panel_x = max(6, int(8 * self._scale))
        panel_bottom = max(4, int(4 * self._scale))
        self._panel.setGeometry(panel_x, h - panel_h - panel_bottom, w - panel_x * 2, panel_h)
        self._rebuild_stylesheet()
        self._reload_sprite()

    def _rebuild_stylesheet(self):
        s = self._scale
        font = int(self.BASE_FONT * s)
        name_font = int(self.BASE_NAME_FONT * s)
        input_font = int(self.BASE_INPUT_FONT * s)
        padding = int(self.BASE_PADDING * s)
        radius = int(self.BASE_RADIUS * s)
        btn_size = int(self.BASE_BTN_SIZE * s)
        scrollbar_w = max(4, int(self.BASE_SCROLLBAR_WIDTH * s))
        panel_border, control_border = self._scaled_border_widths(s)

        self._panel.set_border_style(panel_border, "#d4567a")

        self._dialog_box.setStyleSheet(f"""
            color: #4a3040; font-size: {font}px;
            padding: 1px 0 {max(4, int(6 * s))}px 0; background: transparent;
        """)

        self._input.setStyleSheet(f"""
            QLineEdit {{
                background: rgba(255, 255, 255, 0.64);
                border: {control_border}px solid #d4567a;
                border-radius: {radius}px; padding: {int(8*s)}px {padding}px;
                color: #4a3040; font-size: {input_font}px;
            }}
            QLineEdit:focus {{
                border-color: #9b3060;
                background: rgba(255, 252, 254, 0.78);
            }}
        """)

        for btn in self._panel.findChildren(QPushButton):
            btn.setFixedSize(btn_size, btn_size)
            btn_radius = btn_size // 2
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: rgba(255,255,255,0.68);
                    border: {control_border}px solid #d4567a;
                    border-radius: {btn_radius}px; color: #6b4a5a; font-size: {int(14*s)}px;
                }}
                QPushButton:hover {{
                    background: rgba(255,214,224,0.82);
                    border-color: #9b3060;
                }}
            """)

        self._conversation_pane._scroll_area.setStyleSheet(f"""
            QScrollArea {{ background: transparent; border: none; }}
            QScrollBar:vertical {{
                width: {scrollbar_w}px;
                background: rgba(255, 255, 255, 0.12);
            }}
            QScrollBar::handle:vertical {{
                background: rgba(212, 86, 122, 0.36); border-radius: {scrollbar_w//2}px; min-height: 20px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: rgba(155, 48, 96, 0.48);
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0px; }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}
        """)

    def _reload_sprite(self):
        """Reload sprite at current scale."""
        sprite_area_h = int(self.height() * 0.92)
        self._sprite_label.setFixedHeight(self.height())
        self._sprite_label.setContentsMargins(0, 0, 0, -max(10, int(22 * self._scale)))
        target_size = QSize(int(self.width() * 1.04), sprite_area_h)
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
        if self._settings_window is None:
            if self._settings_window_factory is not None:
                self._settings_window = self._settings_window_factory()
            else:
                from ui.settings.window import SettingsWindow
                self._settings_window = SettingsWindow()
            if hasattr(self._settings_window, "set_close_callback"):
                self._settings_window.set_close_callback(self._clear_settings_window_ref)
        self._settings_window.show()
        if hasattr(self._settings_window, "raise_"):
            self._settings_window.raise_()
        if hasattr(self._settings_window, "activateWindow"):
            self._settings_window.activateWindow()

    def _clear_settings_window_ref(self):
        self._settings_window = None

    @staticmethod
    def _create_tts_adapter(tts_config: TTSConfig | None):
        if tts_config is None:
            return None
        if tts_config.engine == "gptsovits":
            return GPTSoVITSAdapter(tts_config)
        return None

    @staticmethod
    def _normalize_tts_lang(language: str) -> str:
        normalized = language.strip()
        if not normalized:
            return ""
        return GPTSoVITSAdapter._normalize_prompt_lang(normalized)

    @staticmethod
    def _is_neutral_tts_char(char: str) -> bool:
        if char.isspace() or char.isdigit():
            return True
        return unicodedata.category(char).startswith(("P", "S"))

    @staticmethod
    def _is_cjk(char: str) -> bool:
        codepoint = ord(char)
        return (
            0x3400 <= codepoint <= 0x4DBF
            or 0x4E00 <= codepoint <= 0x9FFF
            or 0xF900 <= codepoint <= 0xFAFF
        )

    @staticmethod
    def _is_hiragana(char: str) -> bool:
        codepoint = ord(char)
        return 0x3040 <= codepoint <= 0x309F

    @staticmethod
    def _is_katakana(char: str) -> bool:
        codepoint = ord(char)
        return 0x30A0 <= codepoint <= 0x30FF or 0x31F0 <= codepoint <= 0x31FF

    @staticmethod
    def _is_hangul(char: str) -> bool:
        codepoint = ord(char)
        return (
            0x1100 <= codepoint <= 0x11FF
            or 0x3130 <= codepoint <= 0x318F
            or 0xAC00 <= codepoint <= 0xD7AF
        )

    @staticmethod
    def _is_ascii_letter(char: str) -> bool:
        return ("a" <= char <= "z") or ("A" <= char <= "Z")

    @classmethod
    def _looks_like_chinese(cls, text: str) -> bool:
        has_cjk = False
        for char in text:
            if cls._is_neutral_tts_char(char):
                continue
            if cls._is_cjk(char):
                has_cjk = True
                continue
            return False
        return has_cjk

    @classmethod
    def _looks_like_english(cls, text: str) -> bool:
        has_ascii_letter = False
        for char in text:
            if cls._is_neutral_tts_char(char):
                continue
            if cls._is_ascii_letter(char):
                has_ascii_letter = True
                continue
            return False
        return has_ascii_letter

    @classmethod
    def _looks_like_japanese(cls, text: str) -> bool:
        has_kana = False
        for char in text:
            if cls._is_neutral_tts_char(char):
                continue
            if cls._is_hiragana(char) or cls._is_katakana(char):
                has_kana = True
                continue
            if cls._is_cjk(char):
                continue
            return False
        return has_kana

    @classmethod
    def _looks_like_korean(cls, text: str) -> bool:
        has_hangul = False
        for char in text:
            if cls._is_neutral_tts_char(char):
                continue
            if cls._is_hangul(char):
                has_hangul = True
                continue
            return False
        return has_hangul

    def _tts_text_matches_output_lang(self, text: str) -> bool:
        if not self._tts_output_lang:
            return True
        if self._tts_output_lang in {"zh", "yue"}:
            return self._looks_like_chinese(text)
        if self._tts_output_lang == "en":
            return self._looks_like_english(text)
        if self._tts_output_lang == "ja":
            return self._looks_like_japanese(text)
        if self._tts_output_lang == "ko":
            return self._looks_like_korean(text)
        return False

    @staticmethod
    def _find_sentence_break(text: str) -> int:
        for index, char in enumerate(text):
            if char in SENTENCE_ENDINGS:
                return index + 1
        return -1

    def _extract_tts_segments(self, flush: bool = False) -> list[str]:
        segments: list[str] = []
        while True:
            cut_index = self._find_sentence_break(self._tts_pending_buffer)
            if cut_index < 0:
                break
            segment = self._tts_pending_buffer[:cut_index].strip()
            self._tts_pending_buffer = self._tts_pending_buffer[cut_index:]
            if segment:
                segments.append(segment)
        if flush and self._tts_pending_buffer.strip():
            segments.append(self._tts_pending_buffer.strip())
            self._tts_pending_buffer = ""
        return segments

    def _enqueue_tts_segment(self, text: str) -> None:
        segment_id = self._next_segment_id
        self._next_segment_id += 1
        if not self._tts_text_matches_output_lang(text):
            self._start_translation_worker(
                self._current_utterance_id,
                segment_id,
                text,
                self._tts_output_lang,
            )
            return
        self._start_tts_worker(self._current_utterance_id, segment_id, text)

    def _start_tts_worker(self, utterance_id: int, segment_id: int, text: str) -> None:
        if self._tts_adapter is None:
            return
        worker = TTSWorker(self._tts_adapter, utterance_id, segment_id, text)
        worker.result_ready.connect(self._handle_tts_result, Qt.ConnectionType.QueuedConnection)
        worker.finished.connect(lambda: self._on_tts_worker_finished(worker))
        self._active_tts_workers.append(worker)
        worker.start()

    def _start_translation_worker(self, utterance_id: int, segment_id: int, text: str, target_lang: str) -> None:
        if not target_lang:
            self._start_tts_worker(utterance_id, segment_id, text)
            return
        worker = TTSTranslationWorker(
            self._translate_tts_text,
            utterance_id,
            segment_id,
            text,
            target_lang,
        )
        worker.result_ready.connect(self._handle_translation_result, Qt.ConnectionType.QueuedConnection)
        worker.finished.connect(lambda: self._on_translation_worker_finished(worker))
        self._active_translation_workers.append(worker)
        worker.start()

    def _on_tts_worker_finished(self, worker: TTSWorker) -> None:
        if worker in self._active_tts_workers:
            self._active_tts_workers.remove(worker)
        worker.deleteLater()

    def _on_translation_worker_finished(self, worker: TTSTranslationWorker) -> None:
        if worker in self._active_translation_workers:
            self._active_translation_workers.remove(worker)
        worker.deleteLater()

    def _begin_new_tts_turn(self) -> None:
        self._current_utterance_id += 1
        self._streamed_assistant_text = ""
        self._tts_pending_buffer = ""
        self._next_segment_id = 0
        self._next_play_id = 0
        self._segment_results.clear()
        self._pending_audio_queue.clear()
        if self._audio_player is not None:
            self._is_audio_playing = False
            self._audio_player.stop()
        self._release_audio_buffer()

    def _complete_tts_segment(self, utterance_id: int, segment_id: int, audio: bytes | None) -> None:
        self._segment_results[(utterance_id, segment_id)] = audio or b""
        self._drain_ready_audio()

    def _handle_tts_result(self, utterance_id: int, segment_id: int, audio: bytes | None) -> None:
        if utterance_id != self._current_utterance_id:
            return
        if audio is None:
            print(f"[TTS] segment {segment_id} synthesis failed")
        self._complete_tts_segment(utterance_id, segment_id, audio)

    def _handle_translation_result(self, utterance_id: int, segment_id: int, translated_text: str | None) -> None:
        if utterance_id != self._current_utterance_id:
            return
        translated = (translated_text or "").strip()
        if not translated:
            print(f"[TTS] segment {segment_id} translation failed")
            self._complete_tts_segment(utterance_id, segment_id, None)
            return
        self._start_tts_worker(utterance_id, segment_id, translated)

    def _translate_tts_text(self, text: str, target_lang: str) -> str | None:
        adapter = getattr(self._llm, "_adapter", None)
        if adapter is None:
            return None
        language_name = {
            "zh": "简体中文",
            "yue": "粤语",
            "en": "English",
            "ja": "日本語",
            "ko": "한국어",
        }.get(target_lang, target_lang)
        messages = [
            {
                "role": "system",
                "content": (
                    f"请把用户提供的文本翻译成{language_name}，"
                    "只输出译文，保留原有语气、语义和标点，不要添加解释。"
                ),
            },
            {"role": "user", "content": text},
        ]
        try:
            translated_parts: list[str] = []
            for chunk in adapter.stream_chat(messages):
                if isinstance(chunk, str):
                    translated_parts.append(chunk)
                elif isinstance(chunk, LLMStreamChunk) and chunk.content:
                    translated_parts.append(chunk.content)
            translated = "".join(translated_parts).strip()
            return translated or None
        except Exception as exc:
            print(f"[TTS] translation request failed: {exc}")
            return None

    def _drain_ready_audio(self) -> None:
        while True:
            key = (self._current_utterance_id, self._next_play_id)
            if key not in self._segment_results:
                break
            audio = self._segment_results.pop(key)
            if audio:
                self._play_audio_bytes(audio)
            self._next_play_id += 1

    def _ensure_audio_backend(self) -> None:
        if self._audio_player is not None:
            return
        self._audio_output = QAudioOutput(self)
        self._audio_player = QMediaPlayer(self)
        self._audio_player.setAudioOutput(self._audio_output)
        self._audio_player.playbackStateChanged.connect(
            self._on_audio_playback_state_changed,
            Qt.ConnectionType.QueuedConnection,
        )

    def _release_audio_buffer(self) -> None:
        if self._audio_buffer is None:
            return
        if self._audio_buffer.isOpen():
            self._audio_buffer.close()
        self._audio_buffer.deleteLater()
        self._audio_buffer = None

    def _start_audio_playback(self, audio: bytes) -> None:
        self._ensure_audio_backend()
        self._release_audio_buffer()
        self._audio_buffer = QBuffer(self)
        self._audio_buffer.setData(QByteArray(audio))
        self._audio_buffer.open(QIODevice.OpenModeFlag.ReadOnly)
        self._audio_player.setSourceDevice(self._audio_buffer)
        self._is_audio_playing = True
        self._audio_player.play()

    def _play_audio_bytes(self, audio: bytes) -> None:
        if not audio:
            return
        if self._is_audio_playing:
            self._pending_audio_queue.append(audio)
            return
        self._start_audio_playback(audio)

    def _on_audio_playback_state_changed(self, state) -> None:
        if state != QMediaPlayer.PlaybackState.StoppedState or not self._is_audio_playing:
            return
        self._is_audio_playing = False
        self._release_audio_buffer()
        if self._pending_audio_queue:
            next_audio = self._pending_audio_queue.pop(0)
            self._start_audio_playback(next_audio)

    # --- Chat logic ---
    def _on_send(self):
        text = self._input.text().strip()
        if not text or self._worker is not None:
            return
        self._input.clear()
        self._begin_new_tts_turn()
        self._set_speaker_name("我", is_user=True)
        self._set_dialog_text(text)

        # 通知主动调度器：用户刚交互
        if self._proactive_scheduler is not None:
            self._proactive_scheduler.notify_interaction()

        self._worker = LLMWorker(self._chat_engine, text)
        self._worker.chunk_received.connect(self._on_chunk, Qt.ConnectionType.QueuedConnection)
        self._worker.finished_signal.connect(self._on_llm_done, Qt.ConnectionType.QueuedConnection)
        self._worker.start()

    def _on_chunk(self, result: ProcessedText):
        if self._name_label.text() == "我" and self._char_name:
            self._set_speaker_name(self._char_name)
        self._set_dialog_text(result.clean_text)
        if self._tts_adapter is not None:
            delta = result.clean_text
            if result.clean_text.startswith(self._streamed_assistant_text):
                delta = result.clean_text[len(self._streamed_assistant_text):]
            self._streamed_assistant_text = result.clean_text
            if delta:
                self._tts_pending_buffer += delta
                for segment in self._extract_tts_segments():
                    self._enqueue_tts_segment(segment)
        if result.emotion:
            self._sprite_mgr.set_emotion(result.emotion)

    def _on_llm_done(self):
        if self._tts_adapter is not None:
            for segment in self._extract_tts_segments(flush=True):
                self._enqueue_tts_segment(segment)
        self._worker = None

    def _on_proactive_message(self, message: str, source: str):
        """收到主动消息：以角色身份显示。"""
        if self._char_name:
            self._set_speaker_name(self._char_name)
        self._set_dialog_text(message)

    def set_memory_store(self, memory_store) -> None:
        self._chat_engine.set_memory_store(memory_store)

    def closeEvent(self, event):
        if self._proactive_scheduler is not None:
            self._proactive_scheduler.stop()
        self._pending_audio_queue.clear()
        if self._audio_player is not None:
            self._is_audio_playing = False
            self._audio_player.stop()
        self._release_audio_buffer()
        super().closeEvent(event)
