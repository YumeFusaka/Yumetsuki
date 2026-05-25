from PySide6.QtWidgets import QApplication

from config.schema import LLMConfig, SystemConfig


def _app() -> QApplication:
    app = QApplication.instance()
    return app or QApplication([])


class _FakeSignal:
    def connect(self, *_args, **_kwargs):
        return None


class _FakeLLMWorker:
    def __init__(self, *_args, **_kwargs):
        self.chunk_received = _FakeSignal()
        self.finished_signal = _FakeSignal()
        self.error_signal = _FakeSignal()
        self.started = False

    def start(self):
        self.started = True


class _FakeLLMManager:
    def __init__(self, *args, **kwargs):
        pass

    def set_character(self, *_args, **_kwargs):
        return None


class _FakeAgentManager:
    def __init__(self, *args, **kwargs):
        pass

    def set_memory_store(self, *_args, **_kwargs):
        return None


class _FakeSpriteManager:
    def __init__(self, *args, **kwargs):
        pass

    def reload(self, *_args, **_kwargs):
        return None

    def load_character(self, *_args, **_kwargs):
        return None

    def set_emotion(self, *_args, **_kwargs):
        return None


def _make_window(monkeypatch, system_config: SystemConfig):
    _app()
    monkeypatch.setattr("ui.chat.window.LLMManager", _FakeLLMManager)
    monkeypatch.setattr("ui.chat.window.AgentManager", _FakeAgentManager)
    monkeypatch.setattr("ui.chat.window.SpriteManager", _FakeSpriteManager)
    monkeypatch.setattr("ui.chat.window.LLMWorker", _FakeLLMWorker)

    from ui.chat.window import ChatWindow

    window = ChatWindow(LLMConfig(), system_config=system_config)
    window._char_name = "樱"
    return window


def test_passive_message_uses_bubble_when_enabled(monkeypatch):
    config = SystemConfig(font_family="Microsoft YaHei", font_size=16)
    config.passive_interaction.enabled = True

    window = _make_window(monkeypatch, config)
    try:
        window._on_proactive_message("今天也要好好休息 <3", "idle")

        assert window._passive_bubble.text() == "今天也要好好休息 <3"
        assert not window._passive_bubble.isHidden()
        assert window._panel.isHidden()
        assert window._passive_bubble_timer.isSingleShot()
    finally:
        window.close()


def test_passive_message_uses_dialog_when_disabled(monkeypatch):
    config = SystemConfig()
    config.passive_interaction.enabled = False

    window = _make_window(monkeypatch, config)
    try:
        window._on_proactive_message("回来啦？", "idle")

        assert window._name_label.text() == "樱"
        assert "回来啦？" in window._dialog_box.text()
        assert window._passive_bubble.isHidden()
        assert not window._panel.isHidden()
    finally:
        window.close()


def test_user_send_restores_main_panel(monkeypatch):
    config = SystemConfig()
    config.passive_interaction.enabled = True

    window = _make_window(monkeypatch, config)
    try:
        window._on_proactive_message("我在这里。", "idle")
        assert not window._passive_bubble.isHidden()
        assert window._panel.isHidden()

        window._input.setText("你好")
        window._on_send()

        assert window._passive_bubble.isHidden()
        assert not window._panel.isHidden()
        assert "你好" in window._dialog_box.text()
    finally:
        window.close()


def test_passive_bubble_uses_configured_width_scale_and_duration(monkeypatch):
    config = SystemConfig(font_family="Microsoft YaHei", font_size=18)
    config.chat_display.bubble_scale = 1.25
    config.passive_interaction.enabled = True
    config.passive_interaction.bubble_max_width = 320
    config.passive_interaction.bubble_duration_seconds = 3

    window = _make_window(monkeypatch, config)
    try:
        window._scale = 1.2
        window._apply_scale()
        window._on_proactive_message("缩放后的气泡", "idle")

        assert window._passive_bubble.maximumWidth() <= int(320 * 1.25 * 1.2)
        assert window._passive_bubble_timer.interval() == 3000
        style = window._passive_bubble.styleSheet()
        assert "#fff5fa" in style
        assert "#d4567a" in style
        assert 'font-family: "Microsoft YaHei"' in style
    finally:
        window.close()


def test_passive_bubble_is_capped_by_window_available_width(monkeypatch):
    config = SystemConfig(font_family="Microsoft YaHei", font_size=18)
    config.chat_display.bubble_scale = 2.0
    config.passive_interaction.enabled = True
    config.passive_interaction.bubble_max_width = 800

    window = _make_window(monkeypatch, config)
    try:
        window._scale = 1.0
        window._apply_scale()
        long_text = "这是一段很长的被动消息，" * 30
        window._on_proactive_message(long_text, "idle")

        margin = max(8, int(14 * window._scale))
        available_width = window.width() - 2 * margin
        geometry = window._passive_bubble.geometry()

        assert geometry.right() <= window.width()
        assert geometry.width() <= available_width
        assert window._passive_bubble.maximumWidth() <= available_width
    finally:
        window.close()
