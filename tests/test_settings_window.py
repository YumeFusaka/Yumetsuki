from PySide6.QtGui import QPalette
from PySide6.QtWidgets import QApplication, QPushButton, QTextEdit

from config.schema import APIConfig
from config.schema import LLMConfig
from main import APP_STYLE
from ui.chat.window import ChatWindow
import ui.settings.pages.api_page as api_page_module
from ui.settings.pages.api_page import APIPage
from ui.settings.window import SettingsWindow


def _app() -> QApplication:
    app = QApplication.instance()
    return app or QApplication([])


def test_save_button_only_visible_on_api_page():
    _app()
    window = SettingsWindow()
    save_btn = next(
        button for button in window.findChildren(QPushButton)
        if button.objectName() == "save-config-button"
    )

    window._switch_page(0)
    assert not save_btn.isHidden()

    window._switch_page(1)
    assert save_btn.isHidden()

    window._switch_page(2)
    assert save_btn.isHidden()

    window._switch_page(3)
    assert save_btn.isHidden()

    window._switch_page(4)
    assert save_btn.isHidden()


def test_settings_window_navigation_includes_conversation_and_system_logs():
    _app()
    window = SettingsWindow()
    labels = [
        button.text()
        for button in window.findChildren(QPushButton)
        if button.isCheckable()
    ]

    assert "📝  对话日志" in labels
    assert "🧪  系统日志" in labels


def test_settings_window_context_menu_uses_sakura_theme():
    _app()
    window = SettingsWindow()

    style = window.styleSheet()
    assert "QMenu" in style
    assert "background: #fffafc" in style
    assert "QMenu::item:selected" in style
    assert "QMenu" in APP_STYLE
    assert "background: #fffafc" in APP_STYLE


def test_settings_window_styles_standard_text_context_menu():
    _app()
    window = SettingsWindow()
    text_edit = QTextEdit(window)

    menu = text_edit.createStandardContextMenu()

    window._apply_menu_theme(menu)

    assert "QMenu" in menu.styleSheet()
    assert "background: #fffafc" in menu.styleSheet()
    assert menu.palette().color(QPalette.ColorRole.Window).name() == "#fffafc"


def test_launch_chat_binds_current_session_to_conversation_log_page(monkeypatch):
    _app()
    captured = {}

    class DummyChatWindow:
        def __init__(self, llm_config, **kwargs):
            self._tts_session_id = "session-xyz"

        def show(self):
            return None

        def set_memory_store(self, memory_store):
            return None

    monkeypatch.setattr("ui.settings.window.ChatWindow", DummyChatWindow)
    monkeypatch.setattr("ui.settings.window.PluginHost", lambda *_: type("P", (), {"load": lambda self: None})())
    monkeypatch.setattr("ui.settings.window.MCPHost", lambda *_: type("M", (), {"connect_all": lambda self: None})())
    monkeypatch.setattr("ui.settings.window.ToolRegistry", lambda **_: type("T", (), {})())

    class DummyLoader:
        def __init__(self, *_args, **_kwargs):
            self.memory_ready = type("S", (), {"connect": lambda self, *_: None})()
            self.memory_failed = type("S", (), {"connect": lambda self, *_: None})()

        def start(self):
            return None

    monkeypatch.setattr("ui.settings.window.MemoryLoaderThread", DummyLoader)

    window = SettingsWindow()
    monkeypatch.setattr(
        window._conversation_log_page,
        "set_session_id",
        lambda session_id: captured.setdefault("session_id", session_id),
        raising=False,
    )

    window._launch_chat()

    assert captured["session_id"] == "session-xyz"


def test_api_page_discards_unsaved_changes_when_switching_away():
    _app()
    window = SettingsWindow()

    original_model = window._config.api.llm.model
    original_temp = int(window._config.api.llm.temperature * 100)

    window._switch_page(0)
    window._api_page._model.setText("temp-model")
    window._api_page._temp_spin.setValue(123)

    window._switch_page(1)
    window._switch_page(0)

    assert window._api_page._model.text() == original_model
    assert window._api_page._temp_spin.value() == original_temp


def test_api_page_browse_tts_reference_audio_updates_input(monkeypatch):
    _app()
    page = APIPage(APIConfig())

    class _FakeFileDialog:
        @staticmethod
        def getOpenFileName(*args, **kwargs):
            return ("D:/voices/ref.wav", "Audio Files (*.wav *.mp3 *.ogg *.flac)")

    monkeypatch.setattr(api_page_module, "QFileDialog", _FakeFileDialog, raising=False)

    page._browse_tts_ref_audio()

    assert page._tts_ref_audio.text() == "D:/voices/ref.wav"


def test_api_page_tts_language_combos_have_presets_and_remain_editable():
    _app()
    page = APIPage(APIConfig())

    prompt_items = [page._tts_prompt_lang.itemText(i) for i in range(page._tts_prompt_lang.count())]
    output_items = [page._tts_output_lang.itemText(i) for i in range(page._tts_output_lang.count())]

    assert page._tts_prompt_lang.isEditable()
    assert page._tts_output_lang.isEditable()
    assert prompt_items == ["zh", "ja", "en", "ko", "yue"]
    assert output_items == ["zh", "ja", "en", "ko", "yue"]
    assert page._tts_prompt_lang_popup_btn.text() == "▼"
    assert page._tts_output_lang_popup_btn.text() == "▼"
    assert "QPushButton#comboPopupBtn" in api_page_module.FORM_STYLE


def test_api_page_tts_reference_mode_apply_and_reset():
    _app()
    config = APIConfig()
    page = APIPage(config)

    assert page._tts_reference_mode.currentData() == "auto"

    page._tts_reference_mode.setCurrentIndex(2)
    page.apply()
    assert config.tts.reference_mode == "session_preload"

    config.tts.reference_mode = "server_managed"
    page.reset()
    assert page._tts_reference_mode.currentData() == "server_managed"


def test_api_page_tts_audio_mode_apply_and_reset():
    _app()
    config = APIConfig()
    page = APIPage(config)

    assert page._tts_audio_mode.currentData() == "auto"

    page._tts_audio_mode.setCurrentIndex(1)
    page.apply()
    assert config.tts.audio_mode == "pcm_stream"

    config.tts.audio_mode = "wav"
    page.reset()
    assert page._tts_audio_mode.currentData() == "wav"


def test_api_page_tts_audio_mode_has_expected_labels():
    _app()
    page = APIPage(APIConfig())

    items = [page._tts_audio_mode.itemText(i) for i in range(page._tts_audio_mode.count())]
    values = [page._tts_audio_mode.itemData(i) for i in range(page._tts_audio_mode.count())]

    assert items == ["自动（推荐）", "PCM流式（低延迟）", "WAV（兼容/调试）"]
    assert values == ["auto", "pcm_stream", "wav"]


def test_api_page_tts_language_and_ref_audio_apply_and_reset():
    _app()
    config = APIConfig()
    page = APIPage(config)

    page._tts_ref_audio.setText("D:/voices/live.wav")
    page._tts_prompt_lang.setCurrentText("ja")
    page._tts_output_lang.setCurrentText("en")
    page.apply()

    assert config.tts.ref_audio_path == "D:/voices/live.wav"
    assert config.tts.prompt_lang == "ja"
    assert config.tts.output_lang == "en"

    config.tts.ref_audio_path = "E:/samples/reset.wav"
    config.tts.prompt_lang = "yue"
    config.tts.output_lang = "ko"
    page.reset()

    assert page._tts_ref_audio.text() == "E:/samples/reset.wav"
    assert page._tts_prompt_lang.currentText() == "yue"
    assert page._tts_output_lang.currentText() == "ko"


class _FakeLLMManager:
    def __init__(self, *args, **kwargs):
        pass

    def set_character(self, *_args, **_kwargs):
        return None


class _FakeAgentManager:
    def __init__(self, *args, **kwargs):
        pass


class _FakeSpriteManager:
    def __init__(self, *args, **kwargs):
        pass

    def reload(self, *_args, **_kwargs):
        return None

    def load_character(self, *_args, **_kwargs):
        return None


class _FakeSettingsWindow:
    def __init__(self):
        self.show_calls = 0
        self.raise_calls = 0
        self.activate_calls = 0
        self._close_callback = None

    def set_close_callback(self, callback):
        self._close_callback = callback

    def show(self):
        self.show_calls += 1

    def raise_(self):
        self.raise_calls += 1

    def activateWindow(self):
        self.activate_calls += 1

    def close(self):
        if self._close_callback is not None:
            self._close_callback()


def test_chat_window_reuses_existing_settings_window(monkeypatch):
    _app()
    monkeypatch.setattr("ui.chat.window.LLMManager", _FakeLLMManager)
    monkeypatch.setattr("ui.chat.window.AgentManager", _FakeAgentManager)
    monkeypatch.setattr("ui.chat.window.SpriteManager", _FakeSpriteManager)

    created = []

    def factory():
        window = _FakeSettingsWindow()
        created.append(window)
        return window

    window = ChatWindow(LLMConfig(), settings_window_factory=factory)

    window._open_settings()
    window._open_settings()

    assert len(created) == 1
    assert created[0].show_calls == 2
    assert created[0].raise_calls == 2
    assert created[0].activate_calls == 2


def test_chat_window_recreates_settings_window_after_close(monkeypatch):
    _app()
    monkeypatch.setattr("ui.chat.window.LLMManager", _FakeLLMManager)
    monkeypatch.setattr("ui.chat.window.AgentManager", _FakeAgentManager)
    monkeypatch.setattr("ui.chat.window.SpriteManager", _FakeSpriteManager)

    created = []

    def factory():
        window = _FakeSettingsWindow()
        created.append(window)
        return window

    window = ChatWindow(LLMConfig(), settings_window_factory=factory)

    window._open_settings()
    created[0].close()
    window._open_settings()

    assert len(created) == 2
