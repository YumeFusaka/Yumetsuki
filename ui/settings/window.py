from pathlib import Path
import gc
import os
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QStackedWidget, QPushButton, QLabel,
)
from PySide6.QtCore import Qt, QThread, Signal, QCoreApplication, QEvent
from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor, QLinearGradient
from config.manager import ConfigManager
from ui.settings.pages.api_page import APIPage
from ui.settings.pages.character_page import CharacterPage
from ui.settings.pages.mcp_page import MCPPage
from ui.settings.pages.plugin_page import PluginPage
from ui.settings.pages.system_page import SystemPage
from ui.settings.pages.memory_page import MemoryPage
from ui.settings.pages.agent_page import AgentPage
from ui.settings.pages.conversation_log_page import ConversationLogPage
from ui.settings.pages.diagnostics_page import DiagnosticsPage
from ui.settings.pages.system_log_page import SystemLogPage
from ui.chat.window import ChatWindow
from core.log_service import LogService
from core.mcp_host import MCPHost
from core.plugin_host import PluginHost
from core.tool_registry import ToolRegistry
from memory.mem0_store import build_local_mem0_store
from ui.settings.feedback import confirm_action, show_feedback
from ui.theme import (
    SAKURA_MENU_STYLE,
    SAKURA_TOOLTIP_STYLE,
    apply_sakura_menu_theme,
    apply_settings_fonts,
    apply_system_appearance,
    install_sakura_menu_theme,
)

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


def _drain_qt_cleanup_events() -> None:
    gc.collect()
    app = QCoreApplication.instance()
    if app is not None:
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        app.processEvents()


class SettingsWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("  🌸  Yumetsuki 设置中心")
        self.setMinimumSize(950, 640)
        self.resize(1100, 720)
        self.setWindowIcon(_create_sakura_icon())
        install_sakura_menu_theme()
        _drain_qt_cleanup_events()
        self.setStyleSheet(f"""
            QMainWindow {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #fff5f7, stop:0.3 #ffebf2,
                    stop:0.7 #fae4f0, stop:1 #f5e1f8);
            }}
            QDialog, QInputDialog, QMessageBox {{
                background: #fff5f7; color: #4a3040;
            }}
            QDialog QLabel, QMessageBox QLabel {{
                color: #4a3040; font-size: 13px;
            }}
            QDialog QLineEdit {{
                background: rgba(255,255,255,0.8);
                border: 1px solid rgba(220,160,180,0.3);
                border-radius: 6px; padding: 6px 10px;
                color: #4a3040;
            }}
            QDialog QLineEdit:focus {{ border-color: #d4567a; }}
            QDialog QPushButton {{
                background: rgba(255,200,210,0.4);
                border: 1px solid rgba(220,160,180,0.3);
                border-radius: 6px; padding: 6px 16px;
                color: #6b4a5a; font-size: 13px;
            }}
            QDialog QPushButton:hover {{ background: rgba(255,154,162,0.4); }}
            * {{ outline: none; }}
            *:focus {{ border-color: #d4567a; }}
            {GLOBAL_SCROLLBAR}
        """ + SAKURA_MENU_STYLE + SAKURA_TOOLTIP_STYLE)

        self._config = ConfigManager()
        self._log_service = LogService(
            log_root=self._config.system.logging.log_root,
            system_flush_interval_ms=self._config.system.logging.system_flush_interval_ms,
            max_events=self._config.system.logging.ui_buffer_limit,
        )
        self._chat_window = None
        self._close_callback = None

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
        pages_info = [
            ("🔑  API", 0),
            ("👤  角色", 1),
            ("🧠  记忆", 2),
            ("🤖  Agent", 5),
            ("🧩  插件", 6),
            ("🔌  MCP", 9),
            ("📝  对话日志", 3),
            ("🧪  平台日志", 4),
            ("🩺  诊断", 7),
            ("⚙  系统", 8),
        ]
        for label, idx in pages_info:
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setProperty("page_index", idx)
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
        self._char_page = CharacterPage(characters_dir, config=self._config)
        self._stack.addWidget(self._char_page)

        self._memory_page = MemoryPage(self._config.memory)
        self._stack.addWidget(self._memory_page)

        self._conversation_log_page = ConversationLogPage(self._log_service)
        self._stack.addWidget(self._conversation_log_page)

        self._system_log_page = SystemLogPage(self._log_service)
        self._stack.addWidget(self._system_log_page)

        self._agent_page = AgentPage(self._config.agent, config=self._config)
        self._stack.addWidget(self._agent_page)

        self._plugin_page = PluginPage(config=self._config)
        self._stack.addWidget(self._plugin_page)

        self._diagnostics_page = DiagnosticsPage(self._config, self._log_service)
        self._stack.addWidget(self._diagnostics_page)

        self._system_page = SystemPage(self._config.system)
        self._stack.addWidget(self._system_page)

        self._mcp_page = MCPPage(config=self._config)
        self._stack.addWidget(self._mcp_page)

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

        self._launch_btn = QPushButton("🚀 启动对话")
        self._launch_btn.setStyleSheet("""
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
        self._launch_btn.clicked.connect(self._launch_chat)
        bottom_layout.addWidget(self._launch_btn)
        bottom_layout.addStretch()

        self._save_btn = QPushButton("保存配置")
        self._save_btn.setObjectName("save-config-button")
        self._save_btn.setStyleSheet("""
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
        self._save_btn.clicked.connect(self._confirm_save)
        bottom_layout.addWidget(self._save_btn)

        right_layout.addWidget(bottom)
        root.addWidget(right, 1)

        self._switch_page(0)
        self._apply_settings_appearance(refresh_logs=False)

    def _apply_menu_theme(self, menu) -> None:
        apply_sakura_menu_theme(menu)

    def set_chat_window(self, chat_window) -> None:
        self._chat_window = chat_window

    def set_close_callback(self, callback) -> None:
        self._close_callback = callback

    def _apply_page_settings_appearance(self, index: int) -> None:
        page = self._stack.widget(index)
        if page is not None:
            apply_settings_fonts(page, self._config.system)

    def _apply_settings_appearance(self, refresh_logs: bool = True) -> None:
        self._apply_page_settings_appearance(self._stack.currentIndex())
        for button in [*self._nav_buttons, self._launch_btn, self._save_btn]:
            apply_settings_fonts(button, self._config.system)
        if not refresh_logs:
            return
        for page in (self._conversation_log_page, self._system_log_page):
            refresh_appearance = getattr(page, "refresh_appearance", None)
            if callable(refresh_appearance):
                refresh_appearance()

    def showEvent(self, event):
        super().showEvent(event)
        _set_title_bar_color(int(self.winId()))

    def _switch_page(self, index: int):
        current_index = self._stack.currentIndex()
        if current_index == 0 and index != 0:
            self._api_page.reset()
        if current_index == 8 and index != 8:
            self._system_page.reset()
        self._stack.setCurrentIndex(index)
        self._apply_page_settings_appearance(index)
        for btn in self._nav_buttons:
            btn.setChecked(btn.property("page_index") == index)
        self._save_btn.setVisible(index in {0, 8})
        if index == 0:
            self._save_btn.setText("保存 API 配置")
        elif index == 8:
            self._save_btn.setText("保存系统配置")

    def _apply_and_save_api(self):
        self._api_page.apply()
        self._config.save_api()

    def _apply_and_save_system(self):
        previous_system = self._config.system.model_copy(deep=True)
        self._system_page.apply()
        try:
            self._config.save_system()
        except Exception:
            self._config.system = previous_system
            self._system_page._config = self._config.system
            self._system_page.reset()
            if self._chat_window is not None and hasattr(self._chat_window, "apply_system_config"):
                self._chat_window.apply_system_config(self._config.system)
            raise
        app = QCoreApplication.instance()
        if app is not None:
            apply_system_appearance(app, self._config.system)
        self._apply_settings_appearance()
        if self._chat_window is not None and hasattr(self._chat_window, "apply_system_config"):
            self._chat_window.apply_system_config(self._config.system)

    def _confirm_save(self):
        current_index = self._stack.currentIndex()
        if current_index == 0:
            message = "确定保存当前 API 设定吗？"
            save = self._apply_and_save_api
            success = "API 设定已成功保存。"
        elif current_index == 8:
            message = "确定保存当前系统设定吗？"
            save = self._apply_and_save_system
            success = "系统设定已成功保存。"
        else:
            return
        try:
            if not confirm_action(self, "确认保存", message):
                return
            save()
        except Exception as exc:
            show_feedback(self, "保存失败", f"配置保存失败：{exc}", success=False)
            return
        show_feedback(self, "保存成功", success)

    def _launch_chat(self):
        try:
            self._api_page.apply()
        except Exception as exc:
            show_feedback(self, "启动失败", f"读取 API 配置失败，未启动对话：{exc}", success=False)
            return
        # Find first character
        characters_dir = Path(__file__).parent.parent.parent / "data" / "characters"
        char_dir = None
        if characters_dir.is_dir():
            for d in characters_dir.iterdir():
                if d.is_dir() and (d / "prompt.md").exists():
                    char_dir = d
                    break
        plugins_dir = Path(__file__).parent.parent.parent / "plugins"
        plugin_host = PluginHost(plugins_dir)
        plugin_host.load()
        mcp_host = MCPHost(self._config.mcp.servers)
        mcp_host.connect_all()
        tool_registry = ToolRegistry(
            plugin_host=plugin_host,
            mcp_host=mcp_host,
            log_service=self._log_service,
        )
        # Create chat window immediately (memory loaded in background)
        self._chat_window = ChatWindow(
            self._config.api.llm,
            character_dir=char_dir,
            tool_registry=tool_registry,
            memory_store=None,
            user_id=self._config.memory.user_id,
            settings_window_factory=lambda: self,
            agent_config=self._config.agent,
            tts_config=self._config.api.tts,
            system_config=self._config.system,
            asr_config=self._config.api.asr,
            log_service=self._log_service,
        )
        if hasattr(self._conversation_log_page, "set_session_id") and hasattr(self._chat_window, "_tts_session_id"):
            self._conversation_log_page.set_session_id(self._chat_window._tts_session_id)
        if hasattr(self._system_log_page, "set_session_id") and hasattr(self._chat_window, "_tts_session_id"):
            self._system_log_page.set_session_id(self._chat_window._tts_session_id)
        self._chat_window.show()
        show_feedback(self, "启动成功", "桌宠对话窗口已启动，正在加载记忆...")
        # Load memory in background
        self._memory_loader = MemoryLoaderThread(
            self._config.memory,
            self._config.api.llm,
        )
        self._memory_loader.memory_ready.connect(self._on_memory_ready)
        self._memory_loader.memory_failed.connect(self._on_memory_failed)
        self._memory_loader.start()

    def _on_memory_ready(self, memory_store):
        self._chat_window.set_memory_store(memory_store)
        show_feedback(self, "记忆就绪", "对话记忆已加载完成。")

    def _on_memory_failed(self, error_msg):
        show_feedback(self, "记忆加载失败", f"本地记忆未能启动：{error_msg}", success=False)

    def closeEvent(self, event):
        cleared_by_chat_window = False
        if self._chat_window is not None and hasattr(self._chat_window, "_clear_settings_window_ref"):
            self._chat_window._clear_settings_window_ref()
            cleared_by_chat_window = True
        if self._close_callback is not None and not cleared_by_chat_window:
            self._close_callback()
        super().closeEvent(event)


class MemoryLoaderThread(QThread):
    memory_ready = Signal(object)
    memory_failed = Signal(str)

    def __init__(self, memory_config, llm_config):
        super().__init__()
        self._memory_config = memory_config
        self._llm_config = llm_config

    def run(self):
        if not self._memory_config.enabled:
            self.memory_ready.emit(None)
            return
        try:
            store = build_local_mem0_store(self._memory_config, self._llm_config)
            self.memory_ready.emit(store)
        except Exception as exc:
            self.memory_failed.emit(str(exc))
