from PySide6.QtGui import QPalette
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QGroupBox, QLabel, QPushButton, QScrollArea, QSizePolicy, QTextEdit

from config.manager import ConfigManager
from config.schema import APIConfig
from config.schema import LLMConfig
from config.schema import SystemConfig
from main import APP_STYLE
from ui.chat.window import ChatWindow
import ui.settings.pages.api_page as api_page_module
import ui.settings.pages.character_page as character_page_module
import ui.settings.pages.conversation_log_page as conversation_log_page_module
import ui.settings.pages.memory_page as memory_page_module
import ui.settings.pages.plugin_page as plugin_page_module
import ui.settings.pages.system_page as system_page_module
from ui.settings.pages.api_page import APIPage
from ui.settings.pages.system_page import SystemPage
from ui.settings.pages.system_log_page import PAGE_STYLE as SYSTEM_LOG_PAGE_STYLE
from ui.settings.window import SettingsWindow


def _app() -> QApplication:
    app = QApplication.instance()
    return app or QApplication([])


def test_save_button_visible_on_api_and_system_pages_only():
    _app()
    window = SettingsWindow()
    save_btn = next(
        button for button in window.findChildren(QPushButton)
        if button.objectName() == "save-config-button"
    )

    window._switch_page(0)
    assert not save_btn.isHidden()
    assert save_btn.text() == "保存 API 配置"

    window._switch_page(7)
    assert not save_btn.isHidden()
    assert save_btn.text() == "保存系统配置"

    window._switch_page(1)
    assert save_btn.isHidden()

    window._switch_page(2)
    assert save_btn.isHidden()

    window._switch_page(3)
    assert save_btn.isHidden()

    window._switch_page(4)
    assert save_btn.isHidden()


def test_system_save_applies_to_existing_chat_window(monkeypatch):
    _app()
    applied = []
    saved = []

    window = SettingsWindow()
    window._chat_window = type(
        "Chat",
        (),
        {"apply_system_config": lambda self, config: applied.append(config.font_family)},
    )()
    monkeypatch.setattr("ui.settings.window.confirm_action", lambda *_: True)
    monkeypatch.setattr(window._config, "save_system", lambda: saved.append("save"))

    window._system_page._font.setCurrentText("Arial")
    window._switch_page(7)
    window._confirm_save()

    assert window._config.system.font_family == "Arial"
    assert saved == ["save"]
    assert applied == ["Arial"]


def test_settings_window_navigation_uses_current_labels_icons_and_order():
    _app()
    window = SettingsWindow()
    labels = [
        button.text()
        for button in window.findChildren(QPushButton)
        if button.isCheckable()
    ]

    assert labels == [
        "🔑  API",
        "👤  角色",
        "🧠  记忆",
        "🤖  Agent",
        "🧩  插件",
        "📝  对话日志",
        "🧪  平台日志",
        "⚙  系统",
    ]
    assert labels[0][0] != labels[3][0]


def test_settings_window_navigation_click_checks_clicked_target_page():
    _app()
    window = SettingsWindow()
    buttons = [
        button for button in window.findChildren(QPushButton)
        if button.isCheckable()
    ]
    expected_targets = {
        "🔑  API": 0,
        "👤  角色": 1,
        "🧠  记忆": 2,
        "🤖  Agent": 5,
        "🧩  插件": 6,
        "📝  对话日志": 3,
        "🧪  平台日志": 4,
        "⚙  系统": 7,
    }

    for button in buttons:
        button.click()

        assert window._stack.currentIndex() == expected_targets[button.text()]
        assert button.isChecked()
        assert [
            other.text()
            for other in buttons
            if other.isChecked()
        ] == [button.text()]


def test_settings_combo_styles_share_platform_log_combo_style():
    styles = [
        api_page_module.FORM_STYLE,
        memory_page_module.FORM_STYLE,
        conversation_log_page_module.PAGE_STYLE,
        system_page_module.FORM_STYLE,
        character_page_module.DIALOG_STYLE,
        plugin_page_module.DIALOG_STYLE,
        SYSTEM_LOG_PAGE_STYLE,
    ]

    for style in styles:
        assert "QComboBox::down-arrow" in style
        assert "image: url(" in style
        assert "border-top: 6px solid" not in style
        assert "width: 0px" not in style


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
    assert not hasattr(page, "_tts_prompt_lang_popup_btn")
    assert not hasattr(page, "_tts_output_lang_popup_btn")
    assert "QPushButton#comboPopupBtn" not in api_page_module.FORM_STYLE
    assert page._tts_prompt_lang.maximumWidth() == page._tts_output_lang.maximumWidth()
    assert page._tts_prompt_lang.maximumWidth() <= 220


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


def test_api_page_asr_uses_faster_whisper_local_service_fields():
    _app()
    config = APIConfig()
    page = APIPage(config)

    assert [page._asr_engine.itemText(i) for i in range(page._asr_engine.count())] == ["none", "faster_whisper"]
    assert page._asr_url.placeholderText() == "http://127.0.0.1:8000"
    form_labels = [label.text() for label in page.findChildren(QLabel)]
    assert "API URL:" in form_labels
    assert "本地服务:" not in form_labels
    assert not hasattr(page, "_asr_base_url")
    assert not hasattr(page, "_asr_api_key")

    page._asr_engine.setCurrentText("faster_whisper")
    page._asr_url.setText("http://127.0.0.1:9000")
    page._asr_model.setText("small")
    page._asr_language.setCurrentText("auto")
    page._asr_timeout.setValue(15)
    page._asr_silence_threshold.setValue(3)
    page._asr_silence_duration.setValue(900)
    page.apply()

    assert config.asr.engine == "faster_whisper"
    assert config.asr.api_url == "http://127.0.0.1:9000"
    assert config.asr.model == "small"
    assert config.asr.language == "auto"
    assert config.asr.record_timeout_seconds == 15
    assert config.asr.silence_threshold == 0.03
    assert config.asr.silence_duration_ms == 900

    config.asr.engine = "none"
    config.asr.api_url = "http://127.0.0.1:8001"
    config.asr.model = "base"
    config.asr.language = "zh"
    config.asr.record_timeout_seconds = 20
    config.asr.silence_threshold = 0.02
    config.asr.silence_duration_ms = 1200
    page.reset()

    assert page._asr_engine.currentText() == "none"
    assert page._asr_url.text() == "http://127.0.0.1:8001"
    assert page._asr_model.text() == "base"
    assert page._asr_language.currentText() == "zh"
    assert page._asr_timeout.value() == 20
    assert page._asr_silence_threshold.value() == 2
    assert page._asr_silence_duration.value() == 1200


def test_system_page_phase5_display_fields_apply(tmp_path):
    _app()
    config = SystemConfig()
    page = SystemPage(config)

    page._chat_font_scale.setValue(125)
    page._bubble_scale.setValue(110)
    page._idle_threshold.setValue(3)
    page._bubble_max_width.setValue(360)
    page._bubble_duration.setValue(12)
    page.apply()

    assert config.chat_display.font_scale == 1.25
    assert config.chat_display.bubble_scale == 1.1
    assert config.passive_interaction.idle_threshold_seconds == 180
    assert config.passive_interaction.bubble_max_width == 360
    assert config.passive_interaction.bubble_duration_seconds == 12
    assert not hasattr(config.passive_interaction, "enabled")

    reloaded = ConfigManager(config_dir=tmp_path)
    assert reloaded.system.chat_display.font_scale == 1.0
    assert reloaded.system.chat_display.bubble_scale == 1.0
    assert reloaded.system.passive_interaction.idle_threshold_seconds == 300
    assert reloaded.system.passive_interaction.bubble_max_width == 280
    assert reloaded.system.passive_interaction.bubble_duration_seconds == 8


def test_system_page_uses_font_combo_with_system_fonts(monkeypatch):
    _app()
    monkeypatch.setattr(
        "ui.settings.pages.system_page.QFontDatabase.families",
        lambda *_: ["Arial", "Fixedsys", "Microsoft YaHei", "SimSun"],
    )
    monkeypatch.setattr(
        "ui.settings.pages.system_page.QFontDatabase.isSmoothlyScalable",
        lambda family, *_: family != "Fixedsys",
    )
    config = SystemConfig(font_family="Microsoft YaHei")

    page = SystemPage(config)

    assert page._font.isEditable()
    assert [page._font.itemText(i) for i in range(page._font.count())] == [
        "Arial",
        "Fixedsys",
        "Microsoft YaHei",
        "SimSun",
    ]
    assert page._font.currentText() == "Microsoft YaHei"
    assert page._font.itemData(0, Qt.ItemDataRole.FontRole).family() == "Arial"
    assert page._font.itemData(1, Qt.ItemDataRole.FontRole) is None
    assert page._font.itemData(2, Qt.ItemDataRole.FontRole).family() == "Microsoft YaHei"
    assert page._font.font().family() == "Microsoft YaHei"

    page._font.setCurrentText("SimSun")

    assert page._font.font().family() == "SimSun"


def test_system_page_does_not_preview_unscalable_current_font(monkeypatch):
    _app()
    monkeypatch.setattr(
        "ui.settings.pages.system_page.QFontDatabase.families",
        lambda *_: ["Fixedsys", "Microsoft YaHei"],
    )
    monkeypatch.setattr(
        "ui.settings.pages.system_page.QFontDatabase.isSmoothlyScalable",
        lambda family, *_: family != "Fixedsys",
    )

    page = SystemPage(SystemConfig(font_family="Fixedsys"))

    assert page._font.currentText() == "Fixedsys"
    assert page._font.itemData(0, Qt.ItemDataRole.FontRole) is None
    assert page._font.font().family() != "Fixedsys"


def test_system_page_layout_is_scrollable_and_keeps_rows_readable():
    _app()
    page = SystemPage(SystemConfig())
    scroll = page.findChild(QScrollArea)

    assert scroll is not None
    assert scroll.widgetResizable()
    assert page.layout().contentsMargins().top() == 0
    assert page._language.sizePolicy().horizontalPolicy() == QSizePolicy.Policy.Expanding
    assert page._font.sizePolicy().horizontalPolicy() == QSizePolicy.Policy.Expanding
    assert page._font_size.minimumHeight() >= 34
    assert page._idle_threshold.minimumHeight() >= 34
    assert page._bubble_duration.minimumHeight() >= 34
    group_names = [group.title() for group in page.findChildren(QGroupBox)]
    assert group_names == ["基础外观", "聊天显示", "被动状态", "被动气泡", "网络"]


def test_system_page_keeps_bubble_controls_in_single_group():
    _app()
    page = SystemPage(SystemConfig())

    assert page._bubble_group.layout().indexOf(page._bubble_scale) >= 0
    assert page._bubble_group.layout().indexOf(page._bubble_max_width) >= 0
    assert page._bubble_group.layout().indexOf(page._bubble_duration) >= 0
    assert page._display_group.layout().indexOf(page._bubble_scale) < 0
    assert page._passive_group.layout().indexOf(page._bubble_max_width) < 0


def test_system_page_apply_does_not_save_until_settings_window_save(monkeypatch):
    _app()
    saved = []
    monkeypatch.setattr(ConfigManager, "save_system", lambda self: saved.append("save"))

    config = SystemConfig()
    page = SystemPage(config)
    page._font.setCurrentText("Arial")
    page.apply()

    assert config.font_family == "Arial"
    assert saved == []


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
