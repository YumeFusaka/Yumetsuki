from pathlib import Path
import getpass
import re
import time
import unicodedata
import uuid
from html import escape
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QLabel, QPushButton, QMenu,
    QApplication, QSizePolicy, QScrollArea,
)
from PySide6.QtCore import Qt, QThread, Signal, QPoint, QSize, QBuffer, QByteArray, QIODevice, QTimer, QEvent
from PySide6.QtGui import QPixmap, QCursor, QAction, QPainter, QColor, QPainterPath, QBrush, QPen
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from ui.chat.sprite import SpriteManager
from ui.chat.tts_pipeline import TTSPipelineController, TTSSegmentStatus
from core.tool_registry import ToolRegistry
from agent.manager import AgentManager
from llm.manager import LLMManager
from llm.text_processor import ProcessedText, TextProcessor
from llm.adapter import LLMStreamChunk
from config.schema import AgentConfig, ASRConfig, LLMConfig, SystemConfig, TTSConfig
from core.character import load_character, build_system_prompt
from core.log_types import LogChannel, LogLevel, build_log_event
from stt.manager import STTManager
from stt.types import STTResult
from tts.adapters.gptsovits import GPTSoVITSAdapter
from tts.types import TTSAudioFormat, TTSStreamEvent
from ui.chat.audio_backends import PcmStreamPlaybackBackend, WavPlaybackBackend
from ui.chat.stt_recorder import STTRecorder
from ui.text_metrics import clamped_text_width
from vision.manager import VisionManager
from vision.types import OCRResult


SENTENCE_ENDINGS = "。！？；\n"


class LLMWorker(QThread):
    chunk_received = Signal(object)
    finished_signal = Signal()
    error_signal = Signal(str)

    def __init__(self, chat_engine, user_input: str, visual_capture: OCRResult | None = None):
        super().__init__()
        self._chat_engine = chat_engine
        self._input = user_input
        self._visual_capture = visual_capture

    def run(self):
        try:
            for result in self._chat_engine.chat_stream(self._input, visual_capture=self._visual_capture):
                if self.isInterruptionRequested():
                    return
                self.chunk_received.emit(result)
            if not self.isInterruptionRequested():
                self.finished_signal.emit()
        except Exception as exc:
            if not self.isInterruptionRequested():
                self.error_signal.emit(str(exc))


class TTSWorker(QThread):
    event_ready = Signal(int, int, object)

    def __init__(self, adapter, utterance_id: int, segment_id: int, text: str):
        super().__init__()
        self._adapter = adapter
        self._utterance_id = utterance_id
        self._segment_id = segment_id
        self._text = text

    def run(self):
        if self._adapter is None:
            return
        for event in self._adapter.stream_synthesize(self._text):
            if self.isInterruptionRequested():
                return
            self.event_ready.emit(self._utterance_id, self._segment_id, event)


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
        if not self.isInterruptionRequested():
            self.result_ready.emit(self._utterance_id, self._segment_id, translated_text)


class TTSReferencePrepareWorker(QThread):
    result_ready = Signal(object)

    def __init__(self, adapter):
        super().__init__()
        self._adapter = adapter

    def run(self):
        result = None
        if self._adapter is not None:
            result = self._adapter.prepare_reference()
        if not self.isInterruptionRequested():
            self.result_ready.emit(result)


class STTTranscribeWorker(QThread):
    result_ready = Signal(object)

    def __init__(self, manager: STTManager, audio: bytes):
        super().__init__()
        self._manager = manager
        self._audio = audio

    def run(self):
        try:
            result = self._manager.transcribe_wav(self._audio)
        except Exception as exc:
            result = STTResult(text="", error=str(exc))
        if not self.isInterruptionRequested():
            self.result_ready.emit(result)


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
    THREAD_SHUTDOWN_WAIT_MS = 1000
    STT_TRANSCRIBE_TIMEOUT_FALLBACK_SECONDS = 120
    MIN_SCALE = 0.5
    MAX_SCALE = 2.0
    BASE_FONT = 17
    BASE_NAME_FONT = 17
    BASE_INPUT_FONT = 13
    BASE_PADDING = 12
    BASE_RADIUS = 8
    BASE_BTN_SIZE = 34
    BASE_SCROLLBAR_WIDTH = 6
    BASE_PASSIVE_BUBBLE_MIN_WIDTH = 240
    CHARACTER_NAME_COLOR = "#9b3060"
    USER_NAME_COLOR = "#5f6fb2"
    TTS_SOFT_MIN_CHARS = 20
    TTS_SOFT_TARGET_CHARS = 28
    TTS_SOFT_MAX_CHARS = 40
    TTS_TRANSLATION_SOFT_MIN_CHARS = 24
    TTS_TRANSLATION_SOFT_TARGET_CHARS = 32
    TTS_TRANSLATION_SOFT_MAX_CHARS = 48
    TTS_PHONETIC_MARKUP_TAG = "phonetic"
    DISPLAY_FLUSH_INTERVAL_MS = 45
    TTS_EXPRESSIVE_CHARS = set(
        "啊呀哇呜诶欸唉哎咦噫呦哟哦喔嗷呐嗯唔哼嘿哈啦嘛喵"
        "ぁあぃいぅうぇえぉおゃやゅゆょよゎわっー゛゜"
        "ァアィイゥウェエォオャヤュユョヨヮワッー"
        "으아어오우이야여요유와왜에애얘워웅흥하허호후힝냥"
    )

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
        system_config: SystemConfig | None = None,
        asr_config: ASRConfig | None = None,
        log_service=None,
    ):
        super().__init__()
        self._scale = 1.0
        self._system_config = system_config or SystemConfig()
        self._asr_config = asr_config or ASRConfig()
        self._display_font_family = self._system_config.font_family or SystemConfig().font_family
        self._display_font_size = max(1, int(self._system_config.font_size))
        self._display_font_scale = max(0.1, float(self._system_config.chat_display.font_scale))
        self._display_bubble_scale = max(0.1, float(self._system_config.chat_display.bubble_scale))
        self._passive_bubble_chrome_width = 0
        self._speaker_name_color = self.CHARACTER_NAME_COLOR
        self._drag_pos: QPoint | None = None
        self._char_dir = character_dir
        self._settings_window_factory = settings_window_factory
        self._settings_window = None
        self._log_service = log_service
        self._tts_session_id = uuid.uuid4().hex
        self._vision_manager = VisionManager(self._system_config.vision)
        runtime_config = (agent_config or AgentConfig()).tts_runtime
        self._tts_pipeline = TTSPipelineController(
            max_translation_workers=runtime_config.max_translation_workers,
            max_tts_workers=runtime_config.max_tts_workers,
            queue_limit=runtime_config.tts_queue_limit,
            segment_total_timeout_seconds=runtime_config.segment_total_timeout_seconds,
        )
        self._tts_adapter = self._create_tts_adapter(
            tts_config,
            self._tts_session_id,
            runtime_config,
        )
        if self._tts_adapter is not None and hasattr(self._tts_adapter, "_log_service"):
            self._tts_adapter._log_service = log_service
        self._tts_output_lang = self._normalize_tts_lang(tts_config.output_lang if tts_config else "")
        self._streamed_assistant_text = ""
        self._proactive_text_processor = TextProcessor()
        self._tts_committed_text = ""
        self._tts_pending_buffer = ""
        self._current_utterance_id = 0
        self._next_segment_id = 0
        self._next_play_id = 0
        self._segment_results: dict[tuple[int, int], bytes] = {}
        self._wav_segment_buffers: dict[tuple[int, int], bytearray] = {}
        self._segment_states: dict[tuple[int, int], str] = {}
        self._segment_events: dict[tuple[int, int], list[TTSStreamEvent]] = {}
        self._segment_backends: dict[tuple[int, int], object] = {}
        self._active_segment_key: tuple[int, int] | None = None
        self._active_tts_workers = []
        self._active_translation_workers = []
        self._pending_tts_segments: list[tuple[int, int, str]] = []
        self._pending_translation_segments: list[tuple[int, int, str, str]] = []
        self._max_translation_workers = runtime_config.max_translation_workers
        self._max_tts_workers = runtime_config.max_tts_workers
        self._tts_prepare_worker = None
        self._last_user_input = ""
        self._last_rendered_dialog_text = None
        self._pending_dialog_text = None
        self._display_flush_timer = QTimer(self)
        self._display_flush_timer.setSingleShot(True)
        self._display_flush_timer.setInterval(self.DISPLAY_FLUSH_INTERVAL_MS)
        self._display_flush_timer.timeout.connect(self._flush_dialog_text_update)
        self._audio_output = None
        self._audio_player = None
        self._audio_buffer = None
        self._is_audio_playing = False
        self._pending_audio_queue: list[bytes] = []
        self._stt_manager = (
            STTManager(self._asr_config, log_service=log_service, session_id=self._tts_session_id)
            if self._is_stt_enabled()
            else None
        )
        self._stt_recorder = None
        self._stt_worker = None
        self._expired_stt_workers = []
        self._is_stt_recording = False
        self._is_closing = False
        self._is_passive = False
        self._last_interaction_at = time.monotonic()
        self._passive_idle_timer = QTimer(self)
        self._passive_idle_timer.setInterval(1000)
        self._passive_idle_timer.timeout.connect(self._check_passive_idle)
        self._passive_idle_timer.start()
        self._tts_timeout_timer = QTimer(self)
        self._tts_timeout_timer.setInterval(500)
        self._tts_timeout_timer.timeout.connect(self._poll_tts_timeouts)
        self._tts_timeout_timer.start()
        self._start_tts_reference_prepare()

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
        self._llm = LLMManager(
            config,
            tool_registry=tool_registry,
            log_service=log_service,
            session_id=self._tts_session_id,
        )
        self._chat_engine = AgentManager(
            llm_manager=self._llm,
            memory_store=memory_store,
            tool_registry=tool_registry,
            user_id=user_id or getpass.getuser(),
            agent_config=agent_config,
            session_id=self._tts_session_id,
            log_service=log_service,
            vision_manager=self._vision_manager,
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
                can_fire=lambda: self._is_passive,
                parent=self,
            )
            self._proactive_scheduler.proactive_message.connect(
                self._on_proactive_message,
                Qt.ConnectionType.QueuedConnection,
            )
            self._proactive_scheduler.start()

        if character_dir:
            char = load_character(character_dir)
            character_prompt = build_system_prompt(char)
            self._char_name = char.name
            self._set_speaker_name(char.name)
            self._sprite_mgr.load_character(char, character_dir)
            self._llm.set_character(character_prompt)
            if self._proactive_scheduler is not None:
                self._proactive_scheduler.set_character_context(character_prompt)

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

        self._passive_bubble = QLabel(self)
        self._passive_bubble.setTextFormat(Qt.TextFormat.PlainText)
        self._passive_bubble.setWordWrap(True)
        self._passive_bubble.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self._passive_bubble.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Minimum)
        self._passive_bubble.installEventFilter(self)
        self._passive_bubble.hide()
        self._passive_bubble_timer = QTimer(self)
        self._passive_bubble_timer.setSingleShot(True)
        self._passive_bubble_timer.timeout.connect(self._hide_passive_bubble)

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

        status_row = QHBoxLayout()
        status_row.setSpacing(6)
        self._status_label = QLabel("")
        self._status_label.setObjectName("chatStatusLabel")
        self._status_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._status_label.hide()
        status_row.addWidget(self._status_label, 1)

        self._stop_btn = QPushButton("停止")
        self._stop_btn.setObjectName("statusActionButton")
        self._stop_btn.setToolTip("停止当前生成和播报")
        self._stop_btn.clicked.connect(self._cancel_current_turn)
        self._stop_btn.hide()
        status_row.addWidget(self._stop_btn)

        self._retry_btn = QPushButton("重试")
        self._retry_btn.setObjectName("statusActionButton")
        self._retry_btn.setToolTip("重试上一条消息")
        self._retry_btn.clicked.connect(self._retry_last_input)
        self._retry_btn.hide()
        status_row.addWidget(self._retry_btn)

        self._logs_btn = QPushButton("日志")
        self._logs_btn.setObjectName("statusActionButton")
        self._logs_btn.setToolTip("打开设置中心查看平台日志")
        self._logs_btn.clicked.connect(lambda: self._open_settings_page(4))
        self._logs_btn.hide()
        status_row.addWidget(self._logs_btn)
        panel_layout.addLayout(status_row)

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

        self._mic_btn = QPushButton("🎤")
        self._mic_btn.setObjectName("micButton")
        self._mic_btn.setFixedSize(34, 34)
        self._mic_btn.setStyleSheet(self._circle_btn_style())
        self._mic_btn.clicked.connect(self._toggle_stt_recording)
        if self._is_stt_enabled():
            self._mic_btn.setToolTip("语音输入")
        else:
            self._mic_btn.setEnabled(False)
            self._mic_btn.setToolTip("语音输入未启用")
        input_row.addWidget(self._mic_btn)

        self._send_btn = QPushButton("→")
        self._send_btn.setObjectName("sendButton")
        self._send_btn.setAccessibleName("发送")
        self._send_btn.setFixedSize(34, 34)
        self._send_btn.setStyleSheet(self._circle_btn_style("#ff9aaa", "#ffb0be"))
        self._send_btn.setToolTip("发送")
        self._send_btn.clicked.connect(self._on_send_button_clicked)
        input_row.addWidget(self._send_btn)

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
                border-radius: 17px; color: #6b4a5a; font-size: 11px;
                font-weight: 700;
            }}
            QPushButton:hover {{
                background: {hover};
                border-color: #9b3060;
            }}
            QPushButton#micButton[recording="true"] {{
                background: rgba(212, 86, 122, 0.14);
                color: #d4567a;
                border-color: #d4567a;
                font-size: 18px;
                font-weight: 700;
            }}
            QPushButton#micButton[recording="true"]:hover {{
                background: rgba(212, 86, 122, 0.22);
                border-color: #9b3060;
            }}
            QPushButton#sendButton {{
                font-size: 15px;
            }}
        """

    def _set_mic_recording_style(self, recording: bool) -> None:
        self._mic_btn.setProperty("recording", recording)
        self._mic_btn.setStyleSheet(self._circle_btn_style())

    def _set_speaker_name(self, name: str, is_user: bool = False) -> None:
        color = self.USER_NAME_COLOR if is_user else self.CHARACTER_NAME_COLOR
        self._speaker_name_color = color
        font = self._scaled_display_font(self.BASE_NAME_FONT)
        self._name_label.setText(name)
        self._name_label.setStyleSheet(f"""
            color: {color}; font-family: "{self._display_font_family}"; font-size: {font}px; font-weight: bold;
            background: transparent;
        """)

    def _scaled_display_font(self, base_font: int) -> int:
        ratio = base_font / self.BASE_FONT
        return max(1, int(self._display_font_size * ratio * self._display_font_scale * self._scale))

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
        font_family: str | None = None,
        line_height: int = 132,
        paragraph_gap: int = 4,
    ) -> str:
        normalized = ChatWindow._normalize_dialog_text(text)
        family_style = f" font-family: &quot;{escape(font_family, quote=True)}&quot;;" if font_family else ""
        if not normalized:
            return (
                f"<div style='line-height: {line_height}%; color: #4a3040; "
                f"font-size: {font}px;{family_style} margin:0;'></div>"
            )

        paragraphs = normalized.split("\n\n")
        html_parts = []
        for index, paragraph in enumerate(paragraphs):
            margin = "0" if index == len(paragraphs) - 1 else f"0 0 {paragraph_gap}px 0"
            body = escape(paragraph).replace("\n", "<br>")
            html_parts.append(f"<div style='margin:{margin};'>{body}</div>")

        return (
            f"<div style='line-height: {line_height}%; color: #4a3040; "
            f"font-size: {font}px;{family_style}'>{''.join(html_parts)}</div>"
        )

    def _set_dialog_text(self, text: str) -> None:
        if text == self._last_rendered_dialog_text:
            return
        self._last_rendered_dialog_text = text
        font = self._scaled_display_font(self.BASE_FONT)
        paragraph_gap = max(2, int(4 * self._scale))
        html = self._build_dialog_html(
            text,
            font=font,
            font_family=self._display_font_family,
            line_height=132,
            paragraph_gap=paragraph_gap,
        )
        self._dialog_box.setText(html)
        self._conversation_pane.scroll_to_top()

    def _queue_dialog_text_update(self, text: str, *, immediate: bool = False) -> None:
        self._pending_dialog_text = text
        if immediate:
            self._flush_dialog_text_update()
            return
        if not self._display_flush_timer.isActive():
            self._display_flush_timer.start()

    def _flush_dialog_text_update(self) -> None:
        if self._pending_dialog_text is None:
            return
        text = self._pending_dialog_text
        self._pending_dialog_text = None
        self._set_dialog_text(text)

    def _set_chat_status(
        self,
        message: str = "",
        *,
        busy: bool = False,
        error: bool = False,
        can_retry: bool = False,
        show_logs: bool = False,
    ) -> None:
        if (
            self._status_label.text() == message
            and bool(self._stop_btn.isVisible()) == bool(busy)
            and bool(self._retry_btn.isVisible()) == bool(can_retry)
            and bool(self._logs_btn.isVisible()) == bool(show_logs)
            and bool(self._status_label.property("error")) == bool(error)
        ):
            return
        self._status_label.setText(message)
        self._status_label.setProperty("error", error)
        self._status_label.setVisible(bool(message))
        self._stop_btn.setVisible(busy)
        self._retry_btn.setVisible(can_retry)
        self._logs_btn.setVisible(show_logs)
        self._send_btn.setText("×" if busy else "→")
        self._send_btn.setToolTip("停止当前生成" if busy else "发送")
        self._send_btn.setAccessibleName("停止当前生成" if busy else "发送")
        self._rebuild_stylesheet()

    def _clear_chat_status(self) -> None:
        self._set_chat_status("")

    def _on_send_button_clicked(self) -> None:
        if self._has_active_turn_work():
            self._cancel_current_turn()
            return
        self._on_send()

    def _has_active_turn_work(self) -> bool:
        return bool(
            self._worker is not None
            or self._active_tts_workers
            or self._active_translation_workers
            or self._pending_tts_segments
            or self._pending_translation_segments
            or self._segment_backends
            or any(events for events in self._segment_events.values())
            or self._segment_results
            or self._wav_segment_buffers
            or self._is_audio_playing
        )

    def _retry_last_input(self) -> None:
        if self._worker is not None or not self._last_user_input:
            return
        self._input.setText(self._last_user_input)
        self._on_send()

    def _cancel_current_turn(self) -> None:
        had_active_work = self._has_active_turn_work()
        if self._worker is not None:
            self._request_worker_stop(self._worker)
        for worker in [*self._active_tts_workers, *self._active_translation_workers]:
            self._request_worker_stop(worker)
        self._begin_new_tts_turn()
        if had_active_work:
            self._set_chat_status("正在停止当前生成...", busy=True, show_logs=True)
        else:
            self._clear_chat_status()

    def _clear_turn_status_if_idle(self) -> None:
        if self._has_active_turn_work():
            return
        if self._status_label.text() in {"正在停止当前生成...", "正在合成语音..."}:
            self._clear_chat_status()

    def _hide_passive_bubble(self) -> None:
        self._passive_bubble_timer.stop()
        self._passive_bubble.hide()
        if not self._is_passive:
            self._panel.show()

    def _refresh_interaction(self, exit_passive: bool = True) -> None:
        self._last_interaction_at = time.monotonic()
        if exit_passive:
            self._exit_passive_state()

    def _on_passive_bubble_clicked(self) -> None:
        self._refresh_interaction(exit_passive=True)

    def _enter_passive_state(self) -> None:
        self._is_passive = True
        self._panel.hide()

    def _exit_passive_state(self) -> None:
        self._is_passive = False
        self._hide_passive_bubble()
        self._panel.show()

    def _check_passive_idle(self) -> None:
        threshold = max(1, int(self._system_config.passive_interaction.idle_threshold_seconds))
        if time.monotonic() - self._last_interaction_at >= threshold:
            self._enter_passive_state()

    def _show_passive_bubble(self, text: str) -> None:
        config = self._system_config.passive_interaction
        self._panel.hide()
        self._passive_bubble.setText(text)
        self._position_passive_bubble()
        self._passive_bubble.show()
        self._passive_bubble.raise_()
        self._passive_bubble_timer.start(max(1, int(config.bubble_duration_seconds)) * 1000)

    def _passive_bubble_max_width(self) -> int:
        config = self._system_config.passive_interaction
        configured_width = max(80, int(config.bubble_max_width * self._display_bubble_scale * self._scale))
        return min(configured_width, self._passive_bubble_available_width())

    def _passive_bubble_min_width(self) -> int:
        configured_width = int(self.BASE_PASSIVE_BUBBLE_MIN_WIDTH * self._display_bubble_scale * self._scale)
        return min(self._passive_bubble_max_width(), max(1, configured_width))

    def _passive_bubble_text_width(self) -> int:
        return clamped_text_width(
            self._passive_bubble,
            self._passive_bubble.text(),
            min_width=self._passive_bubble_min_width(),
            max_width=self._passive_bubble_max_width(),
            chrome_width=self._passive_bubble_chrome_width,
        )

    def _passive_bubble_margin(self) -> int:
        return max(8, int(14 * self._scale))

    def _passive_bubble_available_width(self) -> int:
        margin = self._passive_bubble_margin()
        return max(1, self.width() - 2 * margin)

    def _position_passive_bubble(self) -> None:
        width = self._passive_bubble_text_width()
        self._passive_bubble.setMinimumWidth(width)
        self._passive_bubble.setMaximumWidth(width)
        self._passive_bubble.adjustSize()
        height = self._passive_bubble.heightForWidth(width) if self._passive_bubble.hasHeightForWidth() else 0
        if height <= 0:
            height = self._passive_bubble.sizeHint().height()
        height = max(1, height)
        margin = self._passive_bubble_margin()
        x = max(margin, (self.width() - width) // 2)
        panel_top = self._panel.geometry().top()
        y = max(margin, min(panel_top, self.height() - height - margin))
        self._passive_bubble.setGeometry(x, y, width, height)

    def _apply_scale(self):
        w = int(self.BASE_WIDTH * self._scale)
        h = int(self.BASE_HEIGHT * self._scale)
        self.setFixedSize(w, h)
        panel_h = int(h * 0.45)
        panel_x = max(6, int(8 * self._scale))
        panel_bottom = max(4, int(4 * self._scale))
        self._panel.setGeometry(panel_x, h - panel_h - panel_bottom, w - panel_x * 2, panel_h)
        self._rebuild_stylesheet()
        self._position_passive_bubble()
        self._reload_sprite()

    def _rebuild_stylesheet(self):
        s = self._scale
        font = self._scaled_display_font(self.BASE_FONT)
        name_font = self._scaled_display_font(self.BASE_NAME_FONT)
        input_font = self._scaled_display_font(self.BASE_INPUT_FONT)
        padding = int(self.BASE_PADDING * s)
        radius = int(self.BASE_RADIUS * s)
        btn_size = int(self.BASE_BTN_SIZE * s)
        scrollbar_w = max(4, int(self.BASE_SCROLLBAR_WIDTH * s))
        panel_border, control_border = self._scaled_border_widths(s)

        self._panel.set_border_style(panel_border, "#d4567a")

        self._dialog_box.setStyleSheet(f"""
            color: #4a3040; font-family: "{self._display_font_family}"; font-size: {font}px;
            padding: 1px 0 {max(4, int(6 * s))}px 0; background: transparent;
        """)
        self._name_label.setStyleSheet(f"""
            color: {self._speaker_name_color}; font-family: "{self._display_font_family}"; font-size: {name_font}px; font-weight: bold;
            background: transparent;
        """)

        self._input.setStyleSheet(f"""
            QLineEdit {{
                background: rgba(255, 255, 255, 0.64);
                border: {control_border}px solid #d4567a;
                border-radius: {radius}px; padding: {int(8*s)}px {padding}px;
                color: #4a3040; font-family: "{self._display_font_family}"; font-size: {input_font}px;
            }}
            QLineEdit:focus {{
                border-color: #9b3060;
                background: rgba(255, 252, 254, 0.78);
            }}
        """)

        for btn in self._panel.findChildren(QPushButton):
            if btn.objectName() == "statusActionButton":
                btn.setFixedHeight(max(24, int(28 * s)))
                btn.setMinimumWidth(max(46, int(48 * s)))
                btn.setMaximumWidth(16777215)
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background: rgba(255,255,255,0.62);
                        border: {control_border}px solid rgba(212, 86, 122, 0.42);
                        border-radius: {max(6, int(8*s))}px;
                        color: #7a3a5a;
                        font-size: {max(10, int(11*s))}px;
                        font-weight: 600;
                        padding: 0 {max(8, int(10*s))}px;
                    }}
                    QPushButton:hover {{
                        background: rgba(255,232,240,0.9);
                        border-color: #9b3060;
                    }}
                """)
                continue
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

        bubble_font = self._scaled_display_font(self.BASE_FONT)
        bubble_padding_y = max(8, int(10 * s))
        bubble_padding_x = max(12, int(14 * s))
        bubble_radius = max(8, int(12 * s))
        self._passive_bubble_chrome_width = bubble_padding_x * 2 + control_border * 2
        self._passive_bubble.setStyleSheet(f"""
            QLabel {{
                background: #fff5fa;
                border: {control_border}px solid #d4567a;
                border-radius: {bubble_radius}px;
                color: #4a3040;
                font-family: "{self._display_font_family}";
                font-size: {bubble_font}px;
                padding: {bubble_padding_y}px {bubble_padding_x}px;
            }}
        """)
        status_color = "#9b3060" if self._status_label.property("error") else "#7a5263"
        status_background = "rgba(255, 235, 242, 0.9)" if self._status_label.property("error") else "rgba(255, 250, 252, 0.72)"
        self._status_label.setStyleSheet(f"""
            QLabel#chatStatusLabel {{
                background: {status_background};
                border: {control_border}px solid rgba(212, 86, 122, 0.24);
                border-radius: {max(6, int(8*s))}px;
                color: {status_color};
                font-family: "{self._display_font_family}";
                font-size: {max(10, int(11*s))}px;
                padding: {max(3, int(4*s))}px {max(8, int(10*s))}px;
            }}
        """)

    def _reload_sprite(self):
        """Reload sprite at current scale."""
        sprite_area_h = int(self.height() * 0.92)
        self._sprite_label.setFixedHeight(self.height())
        self._sprite_label.setContentsMargins(0, 0, 0, -max(10, int(22 * self._scale)))
        target_size = QSize(int(self.width() * 1.04), sprite_area_h)
        self._sprite_mgr.reload(target_size)

    # --- Dragging ---
    def eventFilter(self, watched, event):
        if watched is self._passive_bubble and event.type() == QEvent.Type.MouseButtonPress:
            if event.button() == Qt.MouseButton.LeftButton:
                self._on_passive_bubble_clicked()
                event.accept()
                return True
        return super().eventFilter(watched, event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._refresh_interaction(exit_passive=False)
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
        self._refresh_interaction(exit_passive=False)
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

        passive_action = menu.addAction("退出被动状态" if self._is_passive else "进入被动状态")
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
        elif action == passive_action:
            if self._is_passive:
                self._refresh_interaction()
            else:
                self._enter_passive_state()
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
        self._refresh_interaction()
        if self._settings_window is None:
            if self._settings_window_factory is not None:
                self._settings_window = self._settings_window_factory()
            else:
                from ui.settings.window import SettingsWindow
                self._settings_window = SettingsWindow()
            if hasattr(self._settings_window, "set_chat_window"):
                self._settings_window.set_chat_window(self)
            if hasattr(self._settings_window, "set_close_callback"):
                self._settings_window.set_close_callback(self._clear_settings_window_ref)
        self._settings_window.show()
        if hasattr(self._settings_window, "raise_"):
            self._settings_window.raise_()
        if hasattr(self._settings_window, "activateWindow"):
            self._settings_window.activateWindow()

    def _open_settings_page(self, index: int) -> None:
        self._open_settings()
        switch_page = getattr(self._settings_window, "_switch_page", None)
        if callable(switch_page):
            switch_page(index)

    def _clear_settings_window_ref(self):
        self._settings_window = None

    @staticmethod
    def _create_tts_adapter(
        tts_config: TTSConfig | None,
        session_id: str | None = None,
        runtime_config=None,
    ):
        if tts_config is None:
            return None
        if tts_config.engine == "gptsovits":
            return GPTSoVITSAdapter(
                tts_config,
                session_id=session_id,
                runtime_config=runtime_config,
            )
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

    @staticmethod
    def _clean_tts_text(text: str) -> str:
        cleaned = re.sub(r"\[emotion:[^\]]+\]", "", text, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return cleaned

    @classmethod
    def _is_tts_expressive_char(cls, char: str) -> bool:
        return char in cls.TTS_EXPRESSIVE_CHARS

    @staticmethod
    def _is_tts_repeatable_sound_char(char: str) -> bool:
        if char in {"~", "～", "ー"}:
            return True
        return unicodedata.category(char).startswith("L")

    @classmethod
    def _looks_like_phonetic_tts_token(cls, token: str) -> bool:
        core = token.strip("~～ー…,.!?;:，。！？；：、")
        if len(core) < 2 or len(core) > 8:
            return False
        if any(not cls._is_tts_repeatable_sound_char(char) for char in core):
            return False
        if re.fullmatch(r"(.{1,2})\1{1,}", core):
            return True
        return all(cls._is_tts_expressive_char(char) for char in core)

    @classmethod
    def _mark_tts_phonetic_spans(cls, text: str) -> str:
        tag = cls.TTS_PHONETIC_MARKUP_TAG

        def replace(match: re.Match[str]) -> str:
            token = match.group(0)
            if cls._looks_like_phonetic_tts_token(token):
                return f"<{tag}>{token}</{tag}>"
            return token

        return re.sub(r"[^\s，。！？；：、,.!?;:]+", replace, text)

    def _build_tts_translation_messages(self, text: str, target_lang: str) -> list[dict[str, str]]:
        language_name = {
            "zh": "简体中文",
            "yue": "粤语",
            "en": "English",
            "ja": "日本語",
            "ko": "한국어",
        }.get(target_lang, target_lang)
        marked_text = self._mark_tts_phonetic_spans(text)
        return [
            {
                "role": "system",
                "content": (
                    f"你在为 TTS 语音合成准备译文。请把用户提供的文本翻译成{language_name}，"
                    "只输出译文，不要添加解释。\n"
                    "必须保留原文的语气、情绪强度、节奏和标点。\n"
                    "对 <phonetic>...</phonetic> 标记的片段，以及任何拟声词、语气词、拖长音、重复音节，"
                    "优先保留发音感觉，可做音译或近音转写，不要只做语义意译。\n"
                    "这类片段如果有重复、长音或停顿，尽量保留对应的重复次数、长短音和节奏。\n"
                    "不要输出任何标签本身。\n"
                    "示例：像“呀呀呀”这样的惊呼，应优先变成目标语言里发音接近的形式，"
                    "而不是替换成普通感叹词。"
                ),
            },
            {"role": "user", "content": marked_text},
        ]

    def _tts_soft_thresholds(self, text: str) -> tuple[int, int, int]:
        if self._tts_output_lang and not self._tts_text_matches_output_lang(text):
            return (
                self.TTS_TRANSLATION_SOFT_MIN_CHARS,
                self.TTS_TRANSLATION_SOFT_TARGET_CHARS,
                self.TTS_TRANSLATION_SOFT_MAX_CHARS,
            )
        return (self.TTS_SOFT_MIN_CHARS, self.TTS_SOFT_TARGET_CHARS, self.TTS_SOFT_MAX_CHARS)

    def _find_soft_sentence_break(self, text: str) -> int:
        cleaned = text.strip()
        if not cleaned:
            return -1
        soft_min, soft_target, soft_max = self._tts_soft_thresholds(cleaned)
        content_len = len(cleaned)
        if content_len < soft_min:
            return -1

        priorities = ["，", "、"] if content_len < soft_target else ["，", "、", "：", ":"]
        candidates = [(index, char) for index, char in enumerate(text) if char in priorities or char == " "]
        for priority in priorities:
            for index, char in reversed(candidates):
                if char != priority:
                    continue
                if len(text[:index].strip()) >= soft_min:
                    return index + 1
        if content_len >= soft_target:
            for index, char in reversed(candidates):
                if char == " " and len(text[:index].strip()) >= soft_min:
                    return index + 1
        if content_len >= soft_max:
            return soft_max
        return -1

    def _next_tts_break(self, text: str) -> int:
        hard_break = self._find_sentence_break(text)
        if hard_break >= 0:
            return hard_break
        return self._find_soft_sentence_break(text)

    def _extract_tts_segments(self, flush: bool = False) -> list[str]:
        segments: list[str] = []
        while True:
            cut_index = self._next_tts_break(self._tts_pending_buffer)
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

    def _refresh_tts_pending_buffer(self, current_text: str) -> None:
        committed_len = len(self._tts_committed_text)
        if current_text.startswith(self._tts_committed_text):
            self._tts_pending_buffer = current_text[committed_len:]
            return
        if committed_len:
            if len(current_text) <= committed_len:
                self._tts_pending_buffer = ""
            else:
                # Prefix drift should never replay already committed content.
                self._tts_pending_buffer = current_text[committed_len:]
            return
        self._tts_pending_buffer = current_text

    def _enqueue_tts_segment(self, text: str) -> None:
        text = self._clean_tts_text(text)
        if not text:
            return
        segment_id = self._next_segment_id
        self._next_segment_id += 1
        needs_translation = not self._tts_text_matches_output_lang(text)
        state = self._tts_pipeline.enqueue_text_segment(
            utterance_id=self._current_utterance_id,
            segment_id=segment_id,
            text=text,
            needs_translation=needs_translation,
        )
        if state.status == TTSSegmentStatus.SKIPPED:
            self._record_log_event(
                channel=LogChannel.SYSTEM,
                level=LogLevel.WARN,
                source="chat.tts",
                event_type="tts.segment_skipped",
                session_id=self._tts_session_id,
                utterance_id=self._current_utterance_id,
                summary=f"segment {segment_id} skipped",
                details={"text": text, "reason": "queue_limit_exceeded"},
            )
            print(f"[TTS] segment {segment_id} skipped: queue limit exceeded")
            return
        self._record_log_event(
            channel=LogChannel.SYSTEM,
            level=LogLevel.INFO,
            source="chat.tts",
            event_type="tts.segment_enqueued",
            session_id=self._tts_session_id,
            utterance_id=self._current_utterance_id,
            summary=f"segment {segment_id} enqueued",
            details={"text": text, "needs_translation": needs_translation},
        )
        if needs_translation:
            if len(self._active_translation_workers) >= self._max_translation_workers:
                self._pending_translation_segments.append(
                    (self._current_utterance_id, segment_id, text, self._tts_output_lang)
                )
                return
            self._start_translation_worker(
                self._current_utterance_id,
                segment_id,
                text,
                self._tts_output_lang,
            )
            return
        if len(self._active_tts_workers) >= self._max_tts_workers:
            self._pending_tts_segments.append((self._current_utterance_id, segment_id, text))
            return
        self._start_tts_worker(self._current_utterance_id, segment_id, text)

    def _record_tts_segment_ready(self, segment: str) -> None:
        self._record_log_event(
            channel=LogChannel.SYSTEM,
            level=LogLevel.INFO,
            source="chat.segmenter",
            event_type="chat.segmenter.segment_ready",
            session_id=self._tts_session_id,
            utterance_id=self._current_utterance_id,
            summary="TTS segment ready",
            details={"text": segment, "committed_length": len(self._tts_committed_text)},
        )

    def _record_log_event(self, **kwargs) -> None:
        if self._log_service is None:
            return
        self._log_service.record(build_log_event(**kwargs))

    def _enqueue_assistant_text_for_tts(self, text: str, *, flush: bool = False) -> None:
        if self._tts_adapter is None:
            return
        self._streamed_assistant_text = text
        self._refresh_tts_pending_buffer(text)
        for segment in self._extract_tts_segments(flush=flush):
            self._tts_committed_text += segment
            self._record_tts_segment_ready(segment)
            self._enqueue_tts_segment(segment)

    def _start_tts_worker(self, utterance_id: int, segment_id: int, text: str) -> None:
        if self._is_closing or self._tts_adapter is None:
            return
        self._tts_pipeline.mark_synthesizing((utterance_id, segment_id), started_at=time.monotonic())
        worker = TTSWorker(self._tts_adapter, utterance_id, segment_id, text)
        worker.event_ready.connect(self._handle_tts_stream_event, Qt.ConnectionType.QueuedConnection)
        worker.finished.connect(lambda: self._on_tts_worker_finished(worker))
        self._active_tts_workers.append(worker)
        worker.start()

    def _start_translation_worker(self, utterance_id: int, segment_id: int, text: str, target_lang: str) -> None:
        if self._is_closing:
            return
        if not target_lang:
            self._tts_pipeline.mark_ready_for_tts((utterance_id, segment_id), text=text)
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
        if not self._is_closing:
            self._start_next_pending_tts_worker()
        self._clear_turn_status_if_idle()

    def _on_translation_worker_finished(self, worker: TTSTranslationWorker) -> None:
        if worker in self._active_translation_workers:
            self._active_translation_workers.remove(worker)
        worker.deleteLater()
        if not self._is_closing:
            self._start_next_pending_translation_worker()
        self._clear_turn_status_if_idle()

    def _start_next_pending_tts_worker(self) -> None:
        if self._is_closing:
            return
        while self._pending_tts_segments and len(self._active_tts_workers) < self._max_tts_workers:
            utterance_id, segment_id, text = self._pending_tts_segments.pop(0)
            self._start_tts_worker(utterance_id, segment_id, text)

    def _start_next_pending_translation_worker(self) -> None:
        if self._is_closing:
            return
        while (
            self._pending_translation_segments
            and len(self._active_translation_workers) < self._max_translation_workers
        ):
            utterance_id, segment_id, text, target_lang = self._pending_translation_segments.pop(0)
            self._start_translation_worker(utterance_id, segment_id, text, target_lang)

    def _start_tts_reference_prepare(self) -> None:
        if self._tts_adapter is None or self._tts_prepare_worker is not None:
            return
        needs_prepare = getattr(self._tts_adapter, "needs_reference_prepare", None)
        if needs_prepare is None or not needs_prepare():
            return
        self._tts_prepare_worker = TTSReferencePrepareWorker(self._tts_adapter)
        self._tts_prepare_worker.result_ready.connect(
            self._on_tts_reference_prepare_result,
            Qt.ConnectionType.QueuedConnection,
        )
        self._tts_prepare_worker.finished.connect(self._on_tts_reference_prepare_finished)
        self._tts_prepare_worker.start()

    def _on_tts_reference_prepare_result(self, prepared: bool | None) -> None:
        if prepared is False:
            print("[TTS] reference prepare failed, adapter will fall back to inline mode")

    def _on_tts_reference_prepare_finished(self) -> None:
        if self._tts_prepare_worker is not None:
            self._tts_prepare_worker.deleteLater()
            self._tts_prepare_worker = None

    def _begin_new_tts_turn(self) -> None:
        self._current_utterance_id += 1
        self._tts_pipeline.begin_turn(self._current_utterance_id)
        self._streamed_assistant_text = ""
        self._tts_committed_text = ""
        self._tts_pending_buffer = ""
        self._next_segment_id = 0
        self._next_play_id = 0
        self._segment_results.clear()
        self._wav_segment_buffers.clear()
        self._segment_states.clear()
        self._segment_events.clear()
        self._stop_all_segment_backends()
        self._active_segment_key = None
        self._pending_audio_queue.clear()
        self._pending_tts_segments.clear()
        self._pending_translation_segments.clear()
        if self._audio_player is not None:
            self._is_audio_playing = False
            self._audio_player.stop()
        self._release_audio_buffer()

    def _complete_tts_segment(self, utterance_id: int, segment_id: int, audio: bytes | None) -> None:
        key = (utterance_id, segment_id)
        if audio:
            self._tts_pipeline.mark_played(key)
        else:
            self._tts_pipeline.mark_failed(key)
        self._segment_results[(utterance_id, segment_id)] = audio or b""
        self._drain_ready_audio()

    def _handle_tts_result(self, utterance_id: int, segment_id: int, audio: bytes | None) -> None:
        if utterance_id != self._current_utterance_id:
            return
        if audio is None:
            print(f"[TTS] segment {segment_id} synthesis failed")
        self._complete_tts_segment(utterance_id, segment_id, audio)

    def _handle_tts_stream_event(
        self,
        utterance_id: int,
        segment_id: int,
        event: TTSStreamEvent,
    ) -> None:
        if utterance_id != self._current_utterance_id:
            return
        key = (utterance_id, segment_id)
        self._segment_events.setdefault(key, []).append(event)
        self._segment_states.setdefault(key, "pending")
        self._advance_ready_segments()

    def _handle_translation_result(self, utterance_id: int, segment_id: int, translated_text: str | None) -> None:
        if utterance_id != self._current_utterance_id:
            return
        translated = (translated_text or "").strip()
        if not translated:
            print(f"[TTS] segment {segment_id} translation failed")
            self._complete_tts_segment(utterance_id, segment_id, None)
            return
        self._record_log_event(
            channel=LogChannel.SYSTEM,
            level=LogLevel.INFO,
            source="chat.tts",
            event_type="tts.translation_completed",
            session_id=self._tts_session_id,
            utterance_id=utterance_id,
            summary=f"segment {segment_id} translation completed",
            details={"segment_id": segment_id, "translated_preview": translated[:80]},
        )
        self._tts_pipeline.mark_ready_for_tts((utterance_id, segment_id), text=translated)
        if len(self._active_tts_workers) >= self._max_tts_workers:
            self._pending_tts_segments.append((utterance_id, segment_id, translated))
            return
        self._start_tts_worker(utterance_id, segment_id, translated)

    def _translate_tts_text(self, text: str, target_lang: str) -> str | None:
        adapter = getattr(self._llm, "_adapter", None)
        if adapter is None:
            return None
        messages = self._build_tts_translation_messages(text, target_lang)
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

    def _advance_ready_segments(self) -> None:
        while True:
            if self._active_segment_key is None:
                key = (self._current_utterance_id, self._next_play_id)
                if key not in self._segment_states and key not in self._segment_events:
                    return
                self._active_segment_key = key
            key = self._active_segment_key
            events = self._segment_events.get(key)
            if not events:
                return
            event = events.pop(0)
            if event.kind == "start" and event.format is not None:
                if event.format.transport == "wav":
                    self._wav_segment_buffers[key] = bytearray()
                    self._segment_states[key] = "buffering_wav"
                    continue
                self._tts_pipeline.mark_streaming(key)
                self._start_segment_backend(key, event.format)
                self._segment_states[key] = "streaming"
                continue
            if event.kind == "chunk" and event.data is not None:
                if self._segment_states.get(key) == "buffering_wav":
                    self._wav_segment_buffers.setdefault(key, bytearray()).extend(event.data)
                    continue
                self._append_segment_chunk(key, event.data)
                continue
            if event.kind == "end":
                if self._segment_states.get(key) == "buffering_wav":
                    wav_bytes = bytes(self._wav_segment_buffers.pop(key, bytearray()))
                    self._segment_states.pop(key, None)
                    self._active_segment_key = None
                    self._complete_tts_segment(key[0], key[1], wav_bytes)
                    self._advance_ready_segments()
                    return
                self._segment_states[key] = "ended"
                self._finish_segment_backend(key)
                return
            if event.kind == "error":
                self._wav_segment_buffers.pop(key, None)
                self._fail_segment(key, event.message)
                continue

    def _start_segment_backend(self, key: tuple[int, int], audio_format: TTSAudioFormat) -> None:
        self._stop_segment_backend(key)
        if audio_format.transport == "pcm_stream":
            backend = PcmStreamPlaybackBackend(self)
        else:
            backend = WavPlaybackBackend(self)
        backend.playback_finished.connect(
            lambda key=key: self._on_segment_playback_finished(key),
            Qt.ConnectionType.QueuedConnection,
        )
        backend.start_stream(audio_format)
        self._segment_backends[key] = backend

    def _append_segment_chunk(self, key: tuple[int, int], data: bytes) -> None:
        backend = self._segment_backends.get(key)
        if backend is None:
            return
        backend.append_chunk(data)

    def _finish_segment_backend(self, key: tuple[int, int]) -> None:
        backend = self._segment_backends.get(key)
        if backend is None:
            self._on_segment_playback_finished(key)
            return
        backend.finish_stream()

    def _on_segment_playback_finished(self, key: tuple[int, int]) -> None:
        if key[0] != self._current_utterance_id:
            return
        self._tts_pipeline.mark_played(key)
        self._segment_states.pop(key, None)
        self._segment_events.pop(key, None)
        self._stop_segment_backend(key)
        if self._active_segment_key == key:
            self._next_play_id += 1
            self._active_segment_key = None
        self._advance_ready_segments()
        self._clear_turn_status_if_idle()

    def _fail_segment(self, key: tuple[int, int], message: str) -> None:
        backend = self._segment_backends.get(key)
        has_started_audio = False
        if backend is not None and hasattr(backend, "has_started_playback"):
            has_started_audio = bool(backend.has_started_playback())
        if not has_started_audio and self._tts_adapter is not None and hasattr(self._tts_adapter, "force_session_audio_mode"):
            self._tts_adapter.force_session_audio_mode("wav")
        print(f"[TTS] segment {key[1]} failed: {message}")
        self._tts_pipeline.mark_failed(key)
        self._segment_states.pop(key, None)
        self._segment_events.pop(key, None)
        self._stop_segment_backend(key)
        if self._active_segment_key == key or key[1] == self._next_play_id:
            self._next_play_id += 1
            self._active_segment_key = None
        self._advance_ready_segments()
        self._clear_turn_status_if_idle()

    def _poll_tts_timeouts(self) -> None:
        for key in self._tts_pipeline.collect_timed_out_segments(time.monotonic()):
            self._fail_segment(key, "segment total timeout")

    def _stop_segment_backend(self, key: tuple[int, int]) -> None:
        backend = self._segment_backends.pop(key, None)
        if backend is None:
            return
        if hasattr(backend, "stop"):
            backend.stop()
        if hasattr(backend, "deleteLater"):
            backend.deleteLater()

    def _stop_all_segment_backends(self) -> None:
        for key in list(self._segment_backends.keys()):
            self._stop_segment_backend(key)

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
            return
        self._clear_turn_status_if_idle()

    def _is_stt_enabled(self) -> bool:
        return (self._asr_config.engine or "none").strip().lower() != "none"

    def _is_stt_worker_busy(self) -> bool:
        return self._stt_worker is not None and (
            not hasattr(self._stt_worker, "isRunning") or self._stt_worker.isRunning()
        )

    def _ensure_stt_recorder(self):
        if self._stt_recorder is not None:
            return self._stt_recorder
        self._stt_recorder = STTRecorder(
            record_timeout_seconds=self._asr_config.record_timeout_seconds,
            silence_threshold=self._asr_config.silence_threshold,
            silence_duration_ms=self._asr_config.silence_duration_ms,
            parent=self,
        )
        self._stt_recorder.audio_ready.connect(
            self._on_stt_audio_ready,
            Qt.ConnectionType.QueuedConnection,
        )
        self._stt_recorder.error.connect(
            self._on_stt_recorder_error,
            Qt.ConnectionType.QueuedConnection,
        )
        return self._stt_recorder

    def _toggle_stt_recording(self) -> None:
        self._refresh_interaction()
        if self._is_stt_recording:
            self._stop_stt_recording()
            return
        self._start_stt_recording()

    def _start_stt_recording(self) -> None:
        if self._is_closing:
            return
        if not self._is_stt_enabled() or self._stt_manager is None:
            self._record_stt_event(
                level=LogLevel.WARN,
                event_type="stt.recording_ignored",
                summary="STT recording ignored",
                details={"reason": "disabled"},
            )
            return
        if self._worker is not None or self._is_stt_worker_busy():
            self._record_stt_event(
                level=LogLevel.WARN,
                event_type="stt.recording_ignored",
                summary="STT recording ignored",
                details={
                    "reason": "busy",
                    "llm_busy": self._worker is not None,
                    "stt_busy": self._is_stt_worker_busy(),
                },
            )
            return
        recorder = self._ensure_stt_recorder()
        recorder.start()
        if not self._is_stt_recorder_active(recorder):
            self._is_stt_recording = False
            self._reset_stt_button()
            self._record_stt_event(
                level=LogLevel.ERROR,
                event_type="stt.recording_start_failed",
                summary="STT recording failed to start",
                details={"engine": self._asr_config.engine},
            )
            return
        self._hide_passive_bubble()
        self._begin_new_tts_turn()
        self._is_stt_recording = True
        self._mic_btn.setText("×")
        self._set_mic_recording_style(True)
        self._mic_btn.setToolTip("停止语音输入")
        self._input.setPlaceholderText("正在听...")
        self._record_stt_event(
            level=LogLevel.INFO,
            event_type="stt.recording_started",
            summary="STT recording started",
            details={
                "engine": self._asr_config.engine,
                "record_timeout_seconds": self._asr_config.record_timeout_seconds,
                "silence_threshold": self._asr_config.silence_threshold,
                "silence_duration_ms": self._asr_config.silence_duration_ms,
            },
        )

    def _is_stt_recorder_active(self, recorder) -> bool:
        return getattr(recorder, "_source", None) is not None and getattr(recorder, "_device", None) is not None

    def _stop_stt_recording(self) -> None:
        if not self._is_stt_recording:
            return
        self._is_stt_recording = False
        self._reset_stt_button()
        if self._stt_recorder is not None:
            self._stt_recorder.stop()
        self._record_stt_event(
            level=LogLevel.INFO,
            event_type="stt.recording_stopped",
            summary="STT recording stopped by user",
            details={},
        )

    def _reset_stt_button(self) -> None:
        self._mic_btn.setText("🎤")
        self._set_mic_recording_style(False)
        self._mic_btn.setToolTip("语音输入" if self._is_stt_enabled() else "语音输入未启用")

    def _on_stt_audio_ready(self, audio: bytes) -> None:
        if self._is_closing:
            return
        self._is_stt_recording = False
        self._reset_stt_button()
        if not audio:
            self._input.setPlaceholderText("没有识别到语音")
            self._record_stt_event(
                level=LogLevel.WARN,
                event_type="stt.audio_empty",
                summary="STT recorder returned empty audio",
                details={},
            )
            return
        if self._stt_manager is None or self._is_stt_worker_busy():
            self._record_stt_event(
                level=LogLevel.WARN,
                event_type="stt.audio_ignored",
                summary="STT audio ignored",
                details={
                    "reason": "busy_or_unavailable",
                    "audio_bytes": len(audio),
                    "stt_busy": self._is_stt_worker_busy(),
                },
            )
            return
        self._input.setPlaceholderText("正在识别...")
        self._stt_worker = self._create_stt_worker(audio)
        self._stt_worker.result_ready.connect(
            lambda result, worker=self._stt_worker: self._on_stt_result_from_worker(worker, result),
            Qt.ConnectionType.QueuedConnection,
        )
        worker = self._stt_worker
        worker.finished.connect(lambda worker=worker: self._on_stt_worker_finished(worker))
        self._stt_worker.start()
        self._record_stt_event(
            level=LogLevel.INFO,
            event_type="stt.transcribe_worker_started",
            summary="STT transcribe worker started",
            details={
                "audio_bytes": len(audio),
                "timeout_seconds": self._stt_transcribe_timeout_seconds(),
            },
        )
        self._start_stt_transcribe_watchdog(worker)

    def _create_stt_worker(self, audio: bytes) -> STTTranscribeWorker:
        return STTTranscribeWorker(self._stt_manager, audio)

    def _on_stt_recorder_error(self, message: str) -> None:
        if self._is_closing:
            return
        self._is_stt_recording = False
        self._reset_stt_button()
        self._input.setPlaceholderText(f"录音失败：{message}")
        self._record_stt_event(
            level=LogLevel.ERROR,
            event_type="stt.recording_failed",
            summary="STT recording failed",
            details={"error": message},
        )

    def _on_stt_result_from_worker(self, worker: STTTranscribeWorker, result: STTResult) -> None:
        if self._stt_worker is not worker:
            self._record_stt_event(
                level=LogLevel.WARN,
                event_type="stt.result_ignored",
                summary="Stale STT result ignored",
                details={"has_error": bool(result.error), "text_length": len(result.text or "")},
            )
            return
        self._on_stt_result(result)

    def _on_stt_result(self, result: STTResult) -> None:
        if self._is_closing:
            return
        self._reset_stt_button()
        if result.error:
            self._input.setPlaceholderText(f"识别失败：{result.error}")
            self._record_stt_event(
                level=LogLevel.ERROR,
                event_type="stt.result_failed",
                summary="STT result failed",
                details={"error": result.error},
            )
            return
        text = (result.text or "").strip()
        if not text:
            self._input.setPlaceholderText("没有识别到语音")
            self._record_stt_event(
                level=LogLevel.WARN,
                event_type="stt.result_empty",
                summary="STT result was empty",
                details={"language": result.language},
            )
            return
        self._record_stt_event(
            level=LogLevel.INFO,
            event_type="stt.result_ready",
            summary="STT result ready",
            details={"language": result.language, "text_length": len(text)},
        )
        self._input.setText(text)
        self._on_send()

    def _on_stt_worker_finished(self, worker: STTTranscribeWorker) -> None:
        was_current = self._stt_worker is worker
        if self._stt_worker is worker:
            self._stt_worker = None
        if worker in self._expired_stt_workers:
            self._expired_stt_workers.remove(worker)
        self._record_stt_event(
            level=LogLevel.INFO,
            event_type="stt.transcribe_worker_finished",
            summary="STT transcribe worker finished",
            details={"was_current": was_current},
        )
        worker.deleteLater()

    def _stt_transcribe_timeout_seconds(self) -> int:
        return max(
            10,
            int(getattr(self._asr_config, "transcribe_timeout_seconds", self.STT_TRANSCRIBE_TIMEOUT_FALLBACK_SECONDS)),
        )

    def _start_stt_transcribe_watchdog(self, worker) -> None:
        QTimer.singleShot(
            self._stt_transcribe_timeout_seconds() * 1000,
            lambda worker=worker: self._on_stt_transcribe_timeout(worker),
        )

    def _on_stt_transcribe_timeout(self, worker) -> None:
        if self._is_closing or self._stt_worker is not worker:
            return
        is_running = not hasattr(worker, "isRunning") or worker.isRunning()
        if not is_running:
            return
        self._request_worker_stop(worker)
        if worker not in self._expired_stt_workers:
            self._expired_stt_workers.append(worker)
        self._stt_worker = None
        self._reset_stt_button()
        self._input.setPlaceholderText("识别超时，请查看平台日志或换用更小模型")
        self._record_stt_event(
            level=LogLevel.ERROR,
            event_type="stt.transcribe_timeout",
            summary="STT transcription timed out",
            details={
                "timeout_seconds": self._stt_transcribe_timeout_seconds(),
                "model_path": getattr(self._asr_config, "model_path", ""),
                "device": getattr(self._asr_config, "device", ""),
                "compute_type": getattr(self._asr_config, "compute_type", ""),
            },
        )

    def _record_stt_event(self, level: LogLevel, event_type: str, summary: str, details: dict) -> None:
        self._record_log_event(
            channel=LogChannel.SYSTEM,
            level=level,
            source="chat.stt",
            event_type=event_type,
            session_id=self._tts_session_id,
            utterance_id=self._current_utterance_id,
            summary=summary,
            details=details,
        )

    # --- Chat logic ---
    def _on_send(self):
        self._refresh_interaction()
        text = self._input.text().strip()
        if not text:
            return
        if self._worker is not None:
            self._set_chat_status("正在回复，可先停止当前生成。", busy=True, show_logs=True)
            return
        self._input.clear()
        self._last_user_input = text
        self._begin_new_tts_turn()
        self._set_chat_status("正在思考...", busy=True)
        self._set_speaker_name("我", is_user=True)
        self._queue_dialog_text_update(text, immediate=True)

        # 通知主动调度器：用户刚交互
        if self._proactive_scheduler is not None:
            self._proactive_scheduler.notify_interaction()

        visual_capture = self._capture_visual_for_user_input(text)
        self._worker = LLMWorker(self._chat_engine, text, visual_capture=visual_capture)
        self._worker.chunk_received.connect(self._on_chunk, Qt.ConnectionType.QueuedConnection)
        self._worker.finished_signal.connect(self._on_llm_done, Qt.ConnectionType.QueuedConnection)
        self._worker.error_signal.connect(self._on_llm_error, Qt.ConnectionType.QueuedConnection)
        if hasattr(self._worker, "finished"):
            worker = self._worker
            worker.finished.connect(lambda worker=worker: self._on_llm_worker_finished(worker))
        self._worker.start()

    def _capture_visual_for_user_input(self, text: str) -> OCRResult | None:
        if not self._chat_engine.should_capture_screen(text):
            return None
        self._set_chat_status("正在读取屏幕...", busy=True)
        result = self._vision_manager.capture_screen_image()
        if result.ok:
            self._set_chat_status("屏幕文字已采集，正在思考...", busy=True)
            return result
        self._set_chat_status("读屏截图失败，已继续发送文本。", busy=True, show_logs=True)
        self._record_log_event(
            channel=LogChannel.SYSTEM,
            level=LogLevel.WARN,
            source="chat.vision",
            event_type="vision.capture_failed",
            session_id=self._tts_session_id,
            utterance_id=self._current_utterance_id,
            summary=f"读屏截图失败: {(result.error or '')[:80]}",
            details={"error": result.error},
        )
        return result

    def _on_chunk(self, result: ProcessedText):
        if self._name_label.text() == "我" and self._char_name:
            self._set_speaker_name(self._char_name)
        self._set_chat_status("正在回复...", busy=True)
        self._queue_dialog_text_update(result.clean_text)
        if self._tts_adapter is not None:
            self._enqueue_assistant_text_for_tts(result.clean_text)
        if result.emotion:
            self._sprite_mgr.set_emotion(result.emotion)

    def _on_llm_done(self):
        self._flush_dialog_text_update()
        if self._tts_adapter is not None:
            for segment in self._extract_tts_segments(flush=True):
                self._tts_committed_text += segment
                self._record_tts_segment_ready(segment)
                self._enqueue_tts_segment(segment)
            if self._active_tts_workers or self._pending_tts_segments or self._active_translation_workers:
                self._set_chat_status("正在合成语音...", busy=True, show_logs=True)
                return
        self._clear_chat_status()

    def _on_llm_error(self, error_message: str):
        self._set_chat_status(
            f"请求失败：{error_message}",
            error=True,
            can_retry=bool(self._last_user_input),
            show_logs=True,
        )
        self._record_log_event(
            channel=LogChannel.SYSTEM,
            level=LogLevel.ERROR,
            source="chat.window",
            event_type="chat.request_failed",
            session_id=self._tts_session_id,
            utterance_id=self._current_utterance_id,
            summary="聊天请求失败",
            details={"error": error_message},
        )

    def _on_llm_worker_finished(self, worker) -> None:
        if self._worker is worker:
            self._worker = None
            if self._status_label.text() in {"正在思考...", "正在回复...", "正在停止当前生成..."}:
                self._clear_chat_status()
        if hasattr(worker, "deleteLater"):
            worker.deleteLater()
        self._clear_turn_status_if_idle()

    def _on_proactive_message(self, message: str, source: str):
        """收到主动消息：以角色身份显示。"""
        if not self._is_passive:
            self._record_log_event(
                channel=LogChannel.SYSTEM,
                level=LogLevel.INFO,
                source="chat.proactive",
                event_type="chat.proactive_message_ignored",
                session_id=self._tts_session_id,
                utterance_id=self._current_utterance_id,
                summary="主动消息因非被动状态被忽略",
                details={
                    "source": source,
                    "text_length": len(message or ""),
                    "passive": self._is_passive,
                },
            )
            return
        processed = self._proactive_text_processor.process(message)
        display_text = processed.clean_text
        self._begin_new_tts_turn()
        self._record_log_event(
            channel=LogChannel.SYSTEM,
            level=LogLevel.INFO,
            source="chat.proactive",
            event_type="chat.proactive_message_received",
            session_id=self._tts_session_id,
            utterance_id=self._current_utterance_id,
            summary="主动消息已进入聊天流程",
            details={
                "source": source,
                "text_length": len(display_text),
                "emotion": processed.emotion or "",
                "passive": self._is_passive,
            },
        )
        if processed.emotion:
            self._sprite_mgr.set_emotion(processed.emotion)
        self._show_passive_bubble(display_text)
        self._enqueue_assistant_text_for_tts(display_text, flush=True)

    def apply_system_config(self, config: SystemConfig) -> None:
        self._system_config = config
        self._vision_manager.update_config(config.vision)
        self._display_font_family = config.font_family or SystemConfig().font_family
        self._display_font_size = max(1, int(config.font_size))
        self._display_font_scale = max(0.1, float(config.chat_display.font_scale))
        self._display_bubble_scale = max(0.1, float(config.chat_display.bubble_scale))
        self._apply_scale()
        if not self._passive_bubble.isHidden():
            self._position_passive_bubble()

    def set_memory_store(self, memory_store) -> None:
        self._chat_engine.set_memory_store(memory_store)

    def _thread_workers(self) -> list[object]:
        workers = [
            self._worker,
            self._stt_worker,
            *self._expired_stt_workers,
            self._tts_prepare_worker,
            *self._active_tts_workers,
            *self._active_translation_workers,
        ]
        seen: set[int] = set()
        unique_workers = []
        for worker in workers:
            if worker is None:
                continue
            worker_id = id(worker)
            if worker_id in seen:
                continue
            seen.add(worker_id)
            unique_workers.append(worker)
        return unique_workers

    @staticmethod
    def _request_worker_stop(worker) -> None:
        if hasattr(worker, "requestInterruption"):
            worker.requestInterruption()
        if hasattr(worker, "quit"):
            worker.quit()

    @staticmethod
    def _wait_worker_stopped(worker, timeout_ms: int) -> bool:
        if hasattr(worker, "isRunning") and not worker.isRunning():
            return True
        if not hasattr(worker, "wait"):
            return True
        return bool(worker.wait(timeout_ms))

    def _shutdown_thread_workers(self, timeout_ms: int) -> bool:
        workers = self._thread_workers()
        for worker in workers:
            self._request_worker_stop(worker)
        all_stopped = True
        for worker in workers:
            if not self._wait_worker_stopped(worker, timeout_ms):
                all_stopped = False
        return all_stopped

    def closeEvent(self, event):
        self._is_closing = True
        if self._proactive_scheduler is not None:
            self._proactive_scheduler.stop()
        if hasattr(self, "_passive_bubble_timer"):
            self._passive_bubble_timer.stop()
        if hasattr(self, "_passive_idle_timer"):
            self._passive_idle_timer.stop()
        if self._stt_recorder is not None:
            self._stt_recorder.cancel()
        self._tts_timeout_timer.stop()
        self._pending_tts_segments.clear()
        self._pending_translation_segments.clear()
        if not self._shutdown_thread_workers(self.THREAD_SHUTDOWN_WAIT_MS):
            event.ignore()
            self.hide()
            QTimer.singleShot(200, self.close)
            return
        self._stop_all_segment_backends()
        self._pending_audio_queue.clear()
        if self._audio_player is not None:
            self._is_audio_playing = False
            self._audio_player.stop()
        self._release_audio_buffer()
        super().closeEvent(event)
