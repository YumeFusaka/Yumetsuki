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

    def should_capture_screen(self, *_args, **_kwargs):
        return False

    def set_memory_store(self, *_args, **_kwargs):
        return None


class _FakeSpriteManager:
    def __init__(self, *args, **kwargs):
        self.emotions = []

    def reload(self, *_args, **_kwargs):
        return None

    def load_character(self, *_args, **_kwargs):
        return None

    def set_emotion(self, *_args, **_kwargs):
        self.emotions.append(_args[0])


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


def test_proactive_message_is_ignored_until_window_is_passive(monkeypatch):
    config = SystemConfig(font_family="Microsoft YaHei", font_size=16)
    config.passive_interaction.idle_threshold_seconds = 300

    window = _make_window(monkeypatch, config)
    try:
        queued_texts = []
        window._enqueue_assistant_text_for_tts = lambda text, *, flush=False: queued_texts.append(text)
        window._on_proactive_message("主动提醒", "idle")

        assert window._passive_bubble.isHidden()
        assert "主动提醒" not in window._dialog_box.text()
        assert queued_texts == []
    finally:
        window.close()


def test_proactive_message_uses_bubble_in_passive_state(monkeypatch):
    config = SystemConfig()

    window = _make_window(monkeypatch, config)
    try:
        window._enter_passive_state()
        window._on_proactive_message("[emotion:温柔]被动提醒", "idle")

        assert not window._passive_bubble.isHidden()
        assert window._panel.isHidden()
        assert window._passive_bubble.text() == "被动提醒"
        assert window._passive_bubble_timer.isSingleShot()
        assert window._sprite_mgr.emotions == ["温柔"]
    finally:
        window.close()


def test_user_send_exits_passive_state(monkeypatch):
    config = SystemConfig()

    window = _make_window(monkeypatch, config)
    try:
        window._enter_passive_state()
        window._input.setText("你好")
        window._on_send()

        assert window._is_passive is False
        assert window._passive_bubble.isHidden()
        assert not window._panel.isHidden()
        assert "你好" in window._dialog_box.text()
    finally:
        window.close()


def test_idle_timer_enters_passive_state(monkeypatch):
    config = SystemConfig()
    config.passive_interaction.idle_threshold_seconds = 1

    window = _make_window(monkeypatch, config)
    try:
        window._last_interaction_at -= 2
        window._check_passive_idle()

        assert window._is_passive is True
        assert window._panel.isHidden()
    finally:
        window.close()


def test_passive_state_keeps_main_panel_hidden_after_bubble_timeout(monkeypatch):
    config = SystemConfig()

    window = _make_window(monkeypatch, config)
    try:
        window._enter_passive_state()
        window._show_passive_bubble("短句")
        window._hide_passive_bubble()

        assert window._is_passive is True
        assert window._passive_bubble.isHidden()
        assert window._panel.isHidden()
    finally:
        window.close()


def test_exit_passive_state_restores_main_panel(monkeypatch):
    config = SystemConfig()

    window = _make_window(monkeypatch, config)
    try:
        window._enter_passive_state()
        window._exit_passive_state()

        assert window._is_passive is False
        assert not window._panel.isHidden()
    finally:
        window.close()


def test_passive_bubble_uses_configured_width_scale_and_duration(monkeypatch):
    config = SystemConfig(font_family="Microsoft YaHei", font_size=18)
    config.chat_display.bubble_scale = 1.25
    config.passive_interaction.bubble_max_width = 320
    config.passive_interaction.bubble_duration_seconds = 3

    window = _make_window(monkeypatch, config)
    try:
        window._scale = 1.2
        window._apply_scale()
        window._enter_passive_state()
        window._on_proactive_message("缩放后的气泡", "idle")

        assert window._passive_bubble.maximumWidth() <= int(320 * 1.25 * 1.2)
        assert window._passive_bubble_timer.interval() == 3000
        style = window._passive_bubble.styleSheet()
        assert "#fff5fa" in style
        assert "#d4567a" in style
        assert 'font-family: "Microsoft YaHei"' in style
    finally:
        window.close()


def test_default_passive_bubble_width_and_font_scale_are_larger():
    config = SystemConfig()

    assert config.chat_display.font_scale == 1.3
    assert config.passive_interaction.bubble_max_width == 600


def test_drag_and_scale_keep_passive_state(monkeypatch):
    config = SystemConfig()
    window = _make_window(monkeypatch, config)
    try:
        window._enter_passive_state()
        window._refresh_interaction(exit_passive=False)

        assert window._is_passive is True
        assert window._panel.isHidden()
    finally:
        window.close()


def test_clicking_passive_bubble_exits_passive_state(monkeypatch):
    config = SystemConfig()
    window = _make_window(monkeypatch, config)
    try:
        window._enter_passive_state()
        window._show_passive_bubble("点我恢复")
        window._on_passive_bubble_clicked()

        assert window._is_passive is False
        assert window._passive_bubble.isHidden()
        assert not window._panel.isHidden()
    finally:
        window.close()


def test_passive_bubble_top_aligns_with_dialog_panel(monkeypatch):
    config = SystemConfig()
    window = _make_window(monkeypatch, config)
    try:
        window._scale = 1.0
        window._apply_scale()
        window._enter_passive_state()
        window._show_passive_bubble("位置测试")

        assert window._passive_bubble.geometry().top() == window._panel.geometry().top()
    finally:
        window.close()


def test_passive_bubble_expands_to_single_line_text_until_max_width(monkeypatch):
    config = SystemConfig(font_family="Microsoft YaHei", font_size=18)
    config.chat_display.bubble_scale = 1.0
    config.passive_interaction.bubble_max_width = 600

    window = _make_window(monkeypatch, config)
    try:
        window._scale = 1.0
        window._apply_scale()
        window._enter_passive_state()
        message = "今天要不要休息一下？"
        window._show_passive_bubble(message)

        available_width = window._passive_bubble_available_width()
        geometry = window._passive_bubble.geometry()
        expected_width = window._passive_bubble_text_width()

        assert geometry.width() == expected_width
        assert expected_width < window._passive_bubble_max_width()
        assert geometry.width() <= available_width
        assert window._passive_bubble.maximumWidth() <= available_width
    finally:
        window.close()


def test_passive_bubble_is_capped_by_window_available_width(monkeypatch):
    config = SystemConfig(font_family="Microsoft YaHei", font_size=18)
    config.chat_display.bubble_scale = 2.0
    config.passive_interaction.bubble_max_width = 800

    window = _make_window(monkeypatch, config)
    try:
        window._scale = 1.0
        window._apply_scale()
        long_text = "这是一段很长的被动消息，" * 30
        window._enter_passive_state()
        window._on_proactive_message(long_text, "idle")

        margin = max(8, int(14 * window._scale))
        available_width = window.width() - 2 * margin
        geometry = window._passive_bubble.geometry()

        assert geometry.right() <= window.width()
        assert geometry.width() <= available_width
        assert window._passive_bubble.maximumWidth() <= available_width
    finally:
        window.close()
