from types import SimpleNamespace

import yaml
from PySide6.QtGui import QCloseEvent, QPalette, QWheelEvent
from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtWidgets import QApplication, QComboBox, QGroupBox, QLabel, QListWidget, QPushButton, QScrollArea, QSizePolicy, QSpinBox, QTextEdit, QWidget

from config.manager import ConfigManager
from config.schema import APIConfig
from config.schema import LLMConfig
from config.schema import MemoryConfig
from config.schema import SystemConfig
from core.mcp_host import MCPServerStatus
from core.plugin_host import PluginStatus
from core.model_catalog import STT_MODELS_DIR, model_path_key, resolve_model_path
from main import APP_STYLE
from ui.chat.window import ChatWindow
import ui.settings.pages.api_page as api_page_module
import ui.settings.pages.character_page as character_page_module
import ui.settings.pages.conversation_log_page as conversation_log_page_module
import ui.settings.pages.memory_page as memory_page_module
import ui.settings.pages.mcp_page as mcp_page_module
import ui.settings.pages.plugin_page as plugin_page_module
import ui.settings.pages.system_page as system_page_module
from ui.settings.pages.api_page import APIPage
from ui.settings.pages.memory_page import MemoryPage
from ui.settings.pages.mcp_page import _format_mcp_status_detail
from ui.settings.pages.plugin_page import _format_plugin_status_detail
from ui.settings.pages.system_page import SystemPage
from ui.settings.pages.system_log_page import PAGE_STYLE as SYSTEM_LOG_PAGE_STYLE
from ui.settings.window import SettingsWindow
from ui.theme import apply_settings_fonts, install_sakura_menu_theme, settings_page_title, sakura_combo_box_style, settings_font_tokens
from vision.types import OCRResult


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


def test_system_save_applies_font_to_settings_window(monkeypatch):
    app = _app()
    saved = []
    window = SettingsWindow()
    monkeypatch.setattr("ui.settings.window.confirm_action", lambda *_: True)
    monkeypatch.setattr(window._config, "save_system", lambda: saved.append("save"))

    window._switch_page(7)
    window._system_page._font.setCurrentText("Courier New")
    window._system_page._font_size.setValue(16)
    window._confirm_save()

    assert saved == ["save"]
    assert app.font().pointSize() == 16
    assert window._system_page._font_size.font().pointSize() <= 16


def test_settings_window_bottom_launch_button_uses_controlled_font_tokens(monkeypatch):
    _app()
    window = SettingsWindow()

    window._config.system.font_size = 24
    window._apply_settings_appearance(refresh_logs=False)

    assert "font-size: 16px" in window._launch_btn.styleSheet()


def test_system_page_discards_unsaved_changes_when_switching_away():
    _app()
    window = SettingsWindow()
    original_font = window._config.system.font_family
    original_size = window._config.system.font_size

    window._switch_page(7)
    window._system_page._font.setCurrentText("Arial")
    window._system_page._font_size.setValue(original_size + 1)
    window._switch_page(1)
    window._switch_page(7)

    assert window._system_page._font.currentText() == original_font
    assert window._system_page._font_size.value() == original_size


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
        "🔌  MCP",
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
        "🔌  MCP": 8,
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
        mcp_page_module.DIALOG_STYLE,
        SYSTEM_LOG_PAGE_STYLE,
    ]

    for style in styles:
        assert "QComboBox::down-arrow" in style
        assert "image: url(" in style
        assert "border-top: 6px solid" not in style
        assert "width: 0px" not in style


def test_plugin_page_formats_plugin_status_detail():
    status = PluginStatus(
        name="demo",
        path="E:/Project/Yumetsuki/plugins/demo",
        loaded=True,
        tools_count=2,
        description="Demo plugin",
        message="loaded",
    )

    text = _format_plugin_status_detail(status)

    assert "名称：demo" in text
    assert "状态：已加载" in text
    assert "工具数量：2" in text
    assert "路径：E:/Project/Yumetsuki/plugins/demo" in text


def test_plugin_page_formats_mcp_status_detail():
    status = MCPServerStatus(
        server="notes",
        transport="sse",
        connected=False,
        message="boom",
        error_type="RuntimeError",
        last_checked_at=1.0,
        tool_names=[],
    )

    text = _format_mcp_status_detail(status)

    assert "名称：notes" in text
    assert "状态：未连接" in text
    assert "错误类型：RuntimeError" in text
    assert "boom" in text


def test_settings_window_context_menu_uses_sakura_theme():
    _app()
    window = SettingsWindow()

    style = window.styleSheet()
    assert "QMenu" in style
    assert "background: #fffafc" in style
    assert "QMenu::item:selected" in style
    assert "QToolTip" in style
    assert "background: #fff0f3" in style
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


def test_api_page_asr_uses_faster_whisper_local_model_fields(monkeypatch):
    _app()
    config = APIConfig()
    page = APIPage(config)

    assert [page._asr_engine.itemText(i) for i in range(page._asr_engine.count())] == ["none", "faster_whisper"]
    assert page._asr_model_path.placeholderText() == "data/models/stt/faster-whisper-large-v3-turbo"
    form_labels = [label.text() for label in page.findChildren(QLabel)]
    assert "模型目录:" in form_labels
    assert not hasattr(page, "_asr_base_url")
    assert not hasattr(page, "_asr_api_key")
    assert not hasattr(page, "_asr_url")

    page._asr_engine.setCurrentText("faster_whisper")
    page._asr_model_path.setCurrentText("data/models/stt/faster-whisper-large-v3-turbo")
    page._asr_device.setCurrentText("cpu")
    page._asr_compute_type.setCurrentText("int8")
    page._asr_language.setCurrentText("auto")
    page._asr_transcribe_timeout.setValue(45)
    page._asr_timeout.setValue(15)
    page._asr_silence_threshold.setValue(3)
    page._asr_silence_duration.setValue(900)
    page.apply()

    assert config.asr.engine == "faster_whisper"
    assert config.asr.model_path == "data/models/stt/faster-whisper-large-v3-turbo"
    assert config.asr.device == "cpu"
    assert config.asr.compute_type == "int8"
    assert config.asr.language == "auto"
    assert config.asr.transcribe_timeout_seconds == 45
    assert config.asr.record_timeout_seconds == 15
    assert config.asr.silence_threshold == 0.03
    assert config.asr.silence_duration_ms == 900

    config.asr.engine = "none"
    config.asr.model_path = "data/models/stt/faster-whisper-large-v3-turbo"
    config.asr.device = "cpu"
    config.asr.compute_type = "default"
    config.asr.language = "zh"
    config.asr.transcribe_timeout_seconds = 120
    config.asr.record_timeout_seconds = 20
    config.asr.silence_threshold = 0.02
    config.asr.silence_duration_ms = 1200
    page.reset()

    assert page._asr_engine.currentText() == "none"
    assert model_path_key(resolve_model_path(page._asr_model_path.currentText(), STT_MODELS_DIR)) == model_path_key(
        resolve_model_path("data/models/stt/faster-whisper-large-v3-turbo", STT_MODELS_DIR)
    )
    assert page._asr_device.currentText() == "cpu"
    assert page._asr_compute_type.currentText() == "default"
    assert page._asr_language.currentText() == "zh"
    assert page._asr_transcribe_timeout.value() == 120
    assert page._asr_timeout.value() == 20
    assert page._asr_silence_threshold.value() == 2
    assert page._asr_silence_duration.value() == 1200

    monkeypatch.setattr(
        "ui.settings.pages.api_page.QFileDialog.getExistingDirectory",
        lambda *_args, **_kwargs: "E:/models/faster-whisper",
    )
    page._browse_asr_model_path()
    assert page._asr_model_path.currentText() == "E:/models/faster-whisper"


def test_api_page_scans_stt_models_from_category_and_legacy_dirs(monkeypatch, tmp_path):
    root = tmp_path / "models"
    categorized = root / "stt" / "categorized-whisper"
    legacy = root / "legacy-whisper"
    embedding = root / "embedding" / "embedding-model"
    for path in (categorized, legacy, embedding):
        path.mkdir(parents=True)
        (path / "config.json").write_text("{}", encoding="utf-8")
    (categorized / "model.bin").write_bytes(b"model")
    (legacy / "model.bin").write_bytes(b"model")
    (embedding / "modules.json").write_text("[]", encoding="utf-8")

    monkeypatch.setattr("core.model_catalog.MODELS_ROOT", root)
    monkeypatch.setattr("ui.settings.pages.api_page.STT_MODELS_DIR", root / "stt")

    page = APIPage(APIConfig())
    items = [page._asr_model_path.itemText(i) for i in range(page._asr_model_path.count())]

    assert str(categorized) in items
    assert str(legacy) in items
    assert str(embedding) not in items


def test_api_page_deduplicates_equivalent_asr_paths(monkeypatch, tmp_path):
    _app()
    root = tmp_path / "models"
    model = root / "faster-whisper"
    model.mkdir(parents=True)
    (model / "config.json").write_text("{}", encoding="utf-8")
    (model / "model.bin").write_bytes(b"model")

    config = APIConfig()
    config.asr.model_path = str(model).replace("\\", "/")

    monkeypatch.setattr("core.model_catalog.MODELS_ROOT", root)
    monkeypatch.setattr("ui.settings.pages.api_page.STT_MODELS_DIR", root / "stt")

    page = APIPage(config)
    equivalent = str(model).replace("/", "\\")
    page._set_asr_model_path(equivalent)
    items = [page._asr_model_path.itemText(i) for i in range(page._asr_model_path.count())]

    assert len({item.lower().replace("\\", "/") for item in items}) == len(items)
    assert page._asr_model_path.count() == 1


def test_api_page_default_stt_path_reuses_legacy_model_dir(monkeypatch, tmp_path):
    _app()
    root = tmp_path / "models"
    legacy = root / "faster-whisper-large-v3-turbo"
    legacy.mkdir(parents=True)
    (legacy / "config.json").write_text("{}", encoding="utf-8")
    (legacy / "model.bin").write_bytes(b"model")

    monkeypatch.setattr("core.model_catalog.MODELS_ROOT", root)
    monkeypatch.setattr("ui.settings.pages.api_page.STT_MODELS_DIR", root / "stt")

    page = APIPage(APIConfig())
    items = [page._asr_model_path.itemText(i) for i in range(page._asr_model_path.count())]

    assert items == [str(legacy)]


def test_api_page_model_combo_items_can_be_removed():
    _app()
    page = APIPage(APIConfig())
    page._asr_model_path.clear()
    page._asr_model_path.addItems(["data/models/a", "data/models/b"])

    page._asr_model_path.remove_item_at(0)

    items = [page._asr_model_path.itemText(i) for i in range(page._asr_model_path.count())]
    assert items == ["data/models/b"]


def test_memory_page_scans_embedding_models_from_category_and_legacy_dirs(monkeypatch, tmp_path):
    root = tmp_path / "models"
    categorized = root / "embedding" / "categorized-embedding"
    legacy = root / "legacy-embedding"
    stt = root / "stt" / "stt-model"
    for path in (categorized, legacy, stt):
        path.mkdir(parents=True)
        (path / "config.json").write_text("{}", encoding="utf-8")
    (categorized / "modules.json").write_text("[]", encoding="utf-8")
    (legacy / "modules.json").write_text("[]", encoding="utf-8")
    (stt / "model.bin").write_bytes(b"model")

    monkeypatch.setattr("core.model_catalog.MODELS_ROOT", root)
    monkeypatch.setattr("ui.settings.pages.memory_page.EMBEDDING_MODELS_DIR", root / "embedding")

    page = MemoryPage(MemoryConfig())
    items = [page._model_combo.itemText(i) for i in range(page._model_combo.count())]

    assert str(categorized) in items
    assert str(legacy) in items
    assert str(stt) not in items


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
    assert reloaded.system.chat_display.font_scale == 1.3
    assert reloaded.system.chat_display.bubble_scale == 1.0
    assert reloaded.system.passive_interaction.idle_threshold_seconds == 300
    assert reloaded.system.passive_interaction.bubble_max_width == 600
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
    original_combo_font = page._font.font().family()

    page._font.setCurrentText("SimSun")

    assert page._font.font().family() == original_combo_font


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


def test_settings_font_tokens_clamp_large_system_size_for_settings_center():
    tokens = settings_font_tokens(SystemConfig(font_family="Courier New", font_size=24))

    assert tokens.family == "Courier New"
    assert tokens.raw == 24
    assert tokens.body == 16
    assert tokens.list == 16
    assert tokens.button == 16
    assert tokens.title == 20


def test_apply_settings_fonts_uses_controlled_sizes_and_keeps_combo_svg_arrow():
    _app()
    root = QWidget()
    title = settings_page_title(QLabel("标题", root))
    button = QPushButton("保存", root)
    item_list = QListWidget(root)
    item_list.addItem("插件条目")
    root.setStyleSheet(
        """
        QLabel { font-size: 22px; }
        QPushButton { font-size: 18px; }
        QListWidget::item { font-size: 12px; }
        """
    )

    apply_settings_fonts(root, SystemConfig(font_family="Courier New", font_size=24))

    assert "font-size: 20px" in title.styleSheet()
    assert "QPushButton { font-size: 16px; }" in root.styleSheet()
    assert item_list.item(0).font().pointSize() == 16
    assert "QListWidget::item { font-size: 16px; }" in root.styleSheet()
    assert "image: url(" in sakura_combo_box_style(16)
    assert "border-top: 6px solid" not in sakura_combo_box_style(16)


def test_apply_settings_fonts_keeps_compact_plugin_and_log_controls_small():
    _app()
    root = QWidget()
    plugin_list = QListWidget(root)
    plugin_list.setObjectName("pluginList")
    plugin_list.setProperty("settingsItemFontRole", "small")
    plugin_list.addItem("插件条目")
    log_button = QPushButton("刷新", root)
    log_button.setObjectName("logActionButton")
    root.setStyleSheet(
        """
        QListWidget#pluginList::item { font-size: 12px; }
        QPushButton#logActionButton { font-size: 12px; }
        QPushButton { font-size: 18px; }
        """
    )

    apply_settings_fonts(root, SystemConfig(font_family="Courier New", font_size=24))

    assert plugin_list.item(0).font().pointSize() == 15
    assert "QListWidget#pluginList::item { font-size: 15px; }" in root.styleSheet()
    assert "QPushButton#logActionButton { font-size: 15px; }" in root.styleSheet()
    assert "QPushButton { font-size: 16px; }" in root.styleSheet()


def _wheel_event(delta: int = 120) -> QWheelEvent:
    return QWheelEvent(
        QPointF(8, 8),
        QPointF(8, 8),
        QPoint(0, 0),
        QPoint(0, delta),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.ScrollUpdate,
        False,
    )


def test_combo_and_spinbox_ignore_wheel_until_focused():
    app = _app()
    install_sakura_menu_theme(app)
    root = QWidget()
    combo = QComboBox(root)
    combo.addItems(["低", "中", "高"])
    spin = QSpinBox(root)
    spin.setRange(0, 10)
    spin.setValue(5)
    root.show()
    app.processEvents()

    combo.clearFocus()
    spin.clearFocus()
    QApplication.sendEvent(combo, _wheel_event(-120))
    QApplication.sendEvent(spin, _wheel_event(-120))

    assert combo.currentIndex() == 0
    assert spin.value() == 5

    combo.setFocus()
    QApplication.sendEvent(combo, _wheel_event(-120))
    assert combo.currentIndex() != 0

    spin.setFocus()
    QApplication.sendEvent(spin, _wheel_event(-120))
    assert spin.value() != 5


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
    assert group_names == ["基础外观", "聊天显示", "被动状态", "被动气泡", "视觉 / OCR", "网络"]


def test_system_page_keeps_bubble_controls_in_single_group():
    _app()
    page = SystemPage(SystemConfig())

    assert page._bubble_group.layout().indexOf(page._bubble_scale) >= 0
    assert page._bubble_group.layout().indexOf(page._bubble_max_width) >= 0
    assert page._bubble_group.layout().indexOf(page._bubble_duration) >= 0
    assert page._display_group.layout().indexOf(page._bubble_scale) < 0
    assert page._passive_group.layout().indexOf(page._bubble_max_width) < 0


def test_system_page_exposes_vision_ocr_settings():
    _app()
    config = SystemConfig()
    page = SystemPage(config)

    engine_values = [page._ocr_engine.itemData(i) for i in range(page._ocr_engine.count())]

    assert page._vision_enabled.isChecked() is False
    assert engine_values == ["rapidocr", "paddleocr"]
    assert page._ocr_engine.currentData() == "rapidocr"
    assert page._ocr_language.currentText() == "ch"
    assert page._vision_max_text.value() == 2000
    assert page._vision_screenshot_dir.text() == "data/vision"
    assert page._vision_explicit_only.isChecked() is True
    assert page._vision_explicit_only.isEnabled() is False
    assert "tesseract" not in engine_values


def test_system_page_apply_updates_vision_config():
    _app()
    config = SystemConfig()
    page = SystemPage(config)

    page._vision_enabled.setChecked(True)
    page._ocr_engine.setCurrentIndex(page._ocr_engine.findData("paddleocr"))
    page._ocr_language.setCurrentText("en")
    page._vision_max_text.setValue(3600)
    page._vision_screenshot_dir.setText("runtime/vision")
    page.apply()

    assert config.vision.enabled is True
    assert config.vision.ocr_engine == "paddleocr"
    assert config.vision.language == "en"
    assert config.vision.max_text_chars == 3600
    assert config.vision.screenshot_dir == "runtime/vision"
    assert config.vision.explicit_trigger_only is True


def test_settings_window_discards_unsaved_vision_changes_when_switching_away():
    _app()
    window = SettingsWindow()

    window._switch_page(7)
    window._system_page._vision_enabled.setChecked(True)
    window._system_page._ocr_engine.setCurrentIndex(window._system_page._ocr_engine.findData("paddleocr"))
    window._system_page._ocr_language.setCurrentText("en")
    window._system_page._vision_max_text.setValue(4000)
    window._system_page._vision_screenshot_dir.setText("runtime/vision")
    window._system_page._vision_explicit_only.setChecked(False)
    window._switch_page(1)
    window._switch_page(7)

    assert window._system_page._vision_enabled.isChecked() == window._config.system.vision.enabled
    assert window._system_page._ocr_engine.currentData() == window._config.system.vision.ocr_engine
    assert window._system_page._ocr_language.currentText() == window._config.system.vision.language
    assert window._system_page._vision_max_text.value() == window._config.system.vision.max_text_chars
    assert window._system_page._vision_screenshot_dir.text() == window._config.system.vision.screenshot_dir
    assert window._system_page._vision_explicit_only.isChecked() == window._config.system.vision.explicit_trigger_only


def test_system_save_persists_vision_settings(monkeypatch):
    _app()
    saved = []
    window = SettingsWindow()
    monkeypatch.setattr("ui.settings.window.confirm_action", lambda *_: True)
    monkeypatch.setattr(window._config, "save_system", lambda: saved.append("save"))

    window._switch_page(7)
    window._system_page._vision_enabled.setChecked(True)
    window._system_page._ocr_engine.setCurrentIndex(window._system_page._ocr_engine.findData("paddleocr"))
    window._system_page._ocr_language.setCurrentText("en")
    window._system_page._vision_max_text.setValue(4200)
    window._system_page._vision_screenshot_dir.setText("runtime/vision")
    window._confirm_save()

    assert window._config.system.vision.enabled is True
    assert window._config.system.vision.ocr_engine == "paddleocr"
    assert window._config.system.vision.language == "en"
    assert window._config.system.vision.max_text_chars == 4200
    assert window._config.system.vision.screenshot_dir == "runtime/vision"
    assert window._config.system.vision.explicit_trigger_only is True
    assert saved == ["save"]


def test_settings_window_system_save_writes_vision_config_to_disk(tmp_path, monkeypatch):
    _app()
    monkeypatch.setattr("ui.settings.window.confirm_action", lambda *_: True)
    monkeypatch.setattr("ui.settings.window.ConfigManager", lambda: ConfigManager(config_dir=tmp_path))
    window = SettingsWindow()

    window._switch_page(7)
    window._system_page._vision_enabled.setChecked(True)
    window._system_page._ocr_engine.setCurrentIndex(window._system_page._ocr_engine.findData("paddleocr"))
    window._system_page._ocr_language.setCurrentText("en")
    window._system_page._vision_max_text.setValue(4200)
    window._system_page._vision_screenshot_dir.setText("runtime/vision")
    window._confirm_save()

    saved = yaml.safe_load((tmp_path / "system_config.yaml").read_text(encoding="utf-8"))
    assert saved["vision"]["enabled"] is True
    assert saved["vision"]["ocr_engine"] == "paddleocr"
    assert saved["vision"]["language"] == "en"
    assert saved["vision"]["max_text_chars"] == 4200
    assert saved["vision"]["screenshot_dir"] == "runtime/vision"
    assert saved["vision"]["explicit_trigger_only"] is True

    reloaded = ConfigManager(config_dir=tmp_path)

    assert reloaded.system.vision.enabled is True
    assert reloaded.system.vision.ocr_engine == "paddleocr"
    assert reloaded.system.vision.language == "en"
    assert reloaded.system.vision.max_text_chars == 4200
    assert reloaded.system.vision.screenshot_dir == "runtime/vision"
    assert reloaded.system.vision.explicit_trigger_only is True


def test_chat_window_injects_vision_manager_into_agent(monkeypatch):
    _app()
    captured = {}
    monkeypatch.setattr("ui.chat.window.LLMManager", _FakeLLMManager)
    monkeypatch.setattr("ui.chat.window.SpriteManager", _FakeSpriteManager)

    class CapturingAgentManager:
        def __init__(self, *args, **kwargs):
            captured["vision_manager"] = kwargs.get("vision_manager")

    monkeypatch.setattr("ui.chat.window.AgentManager", CapturingAgentManager)

    config = SystemConfig()
    window = ChatWindow(LLMConfig(), system_config=config)

    assert captured["vision_manager"] is window._vision_manager
    assert window._vision_manager._config == config.vision
    assert window._vision_manager._config is not config.vision


def test_chat_window_pre_captures_screen_before_starting_llm_worker(monkeypatch):
    _app()
    events = []
    captured = {}
    monkeypatch.setattr("ui.chat.window.LLMManager", _FakeLLMManager)
    monkeypatch.setattr("ui.chat.window.SpriteManager", _FakeSpriteManager)

    class FakeAgentManager:
        def __init__(self, *args, **kwargs):
            pass

        def should_capture_screen(self, text):
            return True

    class FakeWorker:
        def __init__(self, chat_engine, user_input, visual_capture=None):
            events.append("worker_init")
            captured["user_input"] = user_input
            captured["visual_capture"] = visual_capture
            self.chunk_received = type("S", (), {"connect": lambda self, *_: None})()
            self.finished_signal = type("S", (), {"connect": lambda self, *_: None})()
            self.error_signal = type("S", (), {"connect": lambda self, *_: None})()
            self.finished = type("S", (), {"connect": lambda self, *_: None})()

        def start(self):
            events.append("worker_start")
            captured["started"] = True

    monkeypatch.setattr("ui.chat.window.AgentManager", FakeAgentManager)
    monkeypatch.setattr("ui.chat.window.LLMWorker", FakeWorker)
    window = ChatWindow(LLMConfig(), system_config=SystemConfig())
    monkeypatch.setattr(
        window._vision_manager,
        "capture_screen_image",
        lambda: events.append("capture") or OCRResult(ok=True, image_path="data/vision/main-thread.png"),
    )
    window._input.setText("帮我看看屏幕")

    window._on_send()

    assert events == ["capture", "worker_init", "worker_start"]
    assert captured["user_input"] == "帮我看看屏幕"
    assert captured["visual_capture"].image_path == "data/vision/main-thread.png"
    assert captured["started"] is True


def test_chat_window_apply_system_config_updates_vision_manager(monkeypatch):
    _app()
    from vision.ocr import PaddleOCRAdapter

    monkeypatch.setattr("ui.chat.window.LLMManager", _FakeLLMManager)
    monkeypatch.setattr("ui.chat.window.AgentManager", _FakeAgentManager)
    monkeypatch.setattr("ui.chat.window.SpriteManager", _FakeSpriteManager)

    window = ChatWindow(LLMConfig(), system_config=SystemConfig())
    initial_adapter = window._vision_manager._ocr
    new_config = SystemConfig()
    new_config.vision.enabled = True
    new_config.vision.ocr_engine = "paddleocr"

    window.apply_system_config(new_config)

    assert window._vision_manager._config == new_config.vision
    assert window._vision_manager._config is not new_config.vision
    assert window._vision_manager._ocr is not initial_adapter
    assert isinstance(window._vision_manager._ocr, PaddleOCRAdapter)


def test_system_save_updates_existing_chat_window_vision_config(monkeypatch):
    _app()
    from vision.ocr import PaddleOCRAdapter

    monkeypatch.setattr("ui.chat.window.LLMManager", _FakeLLMManager)
    monkeypatch.setattr("ui.chat.window.AgentManager", _FakeAgentManager)
    monkeypatch.setattr("ui.chat.window.SpriteManager", _FakeSpriteManager)
    window = SettingsWindow()
    chat_window = ChatWindow(LLMConfig(), system_config=SystemConfig())
    window._chat_window = chat_window
    monkeypatch.setattr("ui.settings.window.confirm_action", lambda *_: True)
    monkeypatch.setattr(window._config, "save_system", lambda: None)

    window._switch_page(7)
    window._system_page._vision_enabled.setChecked(True)
    window._system_page._ocr_engine.setCurrentIndex(window._system_page._ocr_engine.findData("paddleocr"))
    window._system_page._ocr_language.setCurrentText("en")
    window._confirm_save()

    assert chat_window._vision_manager._config == window._config.system.vision
    assert chat_window._vision_manager._config is not window._config.system.vision
    assert chat_window._vision_manager._config.ocr_engine == "paddleocr"
    assert chat_window._vision_manager._config.language == "en"
    assert isinstance(chat_window._vision_manager._ocr, PaddleOCRAdapter)


def test_system_save_rebuilds_existing_chat_window_vision_adapter_with_shared_config(monkeypatch):
    _app()
    from vision.ocr import PaddleOCRAdapter

    monkeypatch.setattr("ui.chat.window.LLMManager", _FakeLLMManager)
    monkeypatch.setattr("ui.chat.window.AgentManager", _FakeAgentManager)
    monkeypatch.setattr("ui.chat.window.SpriteManager", _FakeSpriteManager)
    window = SettingsWindow()
    chat_window = ChatWindow(LLMConfig(), system_config=window._config.system)
    initial_adapter = chat_window._vision_manager._ocr
    window._chat_window = chat_window
    monkeypatch.setattr("ui.settings.window.confirm_action", lambda *_: True)
    monkeypatch.setattr(window._config, "save_system", lambda: None)

    window._switch_page(7)
    window._system_page._ocr_engine.setCurrentIndex(window._system_page._ocr_engine.findData("paddleocr"))
    window._system_page._ocr_language.setCurrentText("en")
    window._confirm_save()

    assert chat_window._vision_manager._config == window._config.system.vision
    assert chat_window._vision_manager._config is not window._config.system.vision
    assert chat_window._vision_manager._ocr is not initial_adapter
    assert isinstance(chat_window._vision_manager._ocr, PaddleOCRAdapter)


def test_system_save_failure_rolls_back_shared_chat_window_vision_config(monkeypatch):
    _app()

    monkeypatch.setattr("ui.chat.window.LLMManager", _FakeLLMManager)
    monkeypatch.setattr("ui.chat.window.AgentManager", _FakeAgentManager)
    monkeypatch.setattr("ui.chat.window.SpriteManager", _FakeSpriteManager)
    window = SettingsWindow()
    chat_window = ChatWindow(LLMConfig(), system_config=window._config.system)
    initial_adapter = chat_window._vision_manager._ocr
    window._chat_window = chat_window
    monkeypatch.setattr("ui.settings.window.confirm_action", lambda *_: True)

    def fail_save():
        raise RuntimeError("disk full")

    monkeypatch.setattr(window._config, "save_system", fail_save)

    window._switch_page(7)
    original_font = window._config.system.font_family
    window._system_page._font.setCurrentText("Arial")
    window._system_page._vision_enabled.setChecked(True)
    window._system_page._ocr_engine.setCurrentIndex(window._system_page._ocr_engine.findData("paddleocr"))
    window._system_page._ocr_language.setCurrentText("en")
    window._confirm_save()

    assert window._config.system.font_family == original_font
    assert window._system_page._font.currentText() == original_font
    assert window._config.system.vision.enabled is False
    assert window._config.system.vision.ocr_engine == "rapidocr"
    assert chat_window._vision_manager._config == window._config.system.vision
    assert chat_window._vision_manager._config is not window._config.system.vision
    assert chat_window._vision_manager._ocr is initial_adapter


def test_settings_window_close_clears_chat_window_reference():
    _app()
    cleared = []
    window = SettingsWindow()
    window._chat_window = SimpleNamespace(_clear_settings_window_ref=lambda: cleared.append("clear"))

    window.closeEvent(QCloseEvent())

    assert cleared == ["clear"]


def test_settings_window_close_runs_registered_callback():
    _app()
    cleared = []
    window = SettingsWindow()
    window.set_close_callback(lambda: cleared.append("callback"))

    window.closeEvent(QCloseEvent())

    assert cleared == ["callback"]


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


def test_chat_window_binds_real_settings_window_for_save_and_close(monkeypatch):
    _app()
    monkeypatch.setattr("ui.chat.window.LLMManager", _FakeLLMManager)
    monkeypatch.setattr("ui.chat.window.AgentManager", _FakeAgentManager)
    monkeypatch.setattr("ui.chat.window.SpriteManager", _FakeSpriteManager)

    created = []

    class BindingSettingsWindow(SettingsWindow):
        def __init__(self):
            super().__init__()
            created.append(self)

    monkeypatch.setattr("ui.settings.window.SettingsWindow", BindingSettingsWindow)
    window = ChatWindow(LLMConfig())

    window._open_settings()
    settings_window = created[0]
    monkeypatch.setattr("ui.settings.window.confirm_action", lambda *_: True)
    monkeypatch.setattr(settings_window._config, "save_system", lambda: None)

    assert settings_window._chat_window is window
    assert settings_window._config.system.vision.ocr_engine == "rapidocr"

    settings_window._switch_page(7)
    settings_window._system_page._ocr_engine.setCurrentIndex(
        settings_window._system_page._ocr_engine.findData("paddleocr")
    )
    settings_window._confirm_save()

    assert window._vision_manager._config == settings_window._config.system.vision
    assert window._vision_manager._config is not settings_window._config.system.vision
    assert window._vision_manager._config.ocr_engine == "paddleocr"

    settings_window.closeEvent(QCloseEvent())

    assert window._settings_window is None


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
