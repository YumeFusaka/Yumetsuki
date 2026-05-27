import inspect
from types import SimpleNamespace

from PySide6.QtWidgets import QApplication

from config.schema import ASRConfig, LLMConfig, SystemConfig


def _app() -> QApplication:
    app = QApplication.instance()
    return app or QApplication([])


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


def test_panel_height_is_45_percent():
    """对话框 panel 应占窗口高度的 45%。"""
    import ui.chat.window as win_module
    source = inspect.getsource(win_module.ChatWindow._apply_scale)
    assert "0.45" in source or "0.45)" in source, "panel 比例应为 45%"
    assert "0.50" not in source and "0.5)" not in source, "旧的 50% 比例应已移除"


def test_scale_constants_defined():
    """缩放基准常量应存在。"""
    from ui.chat.window import ChatWindow
    assert hasattr(ChatWindow, "BASE_FONT")
    assert hasattr(ChatWindow, "BASE_NAME_FONT")
    assert hasattr(ChatWindow, "BASE_INPUT_FONT")
    assert hasattr(ChatWindow, "BASE_PADDING")
    assert hasattr(ChatWindow, "BASE_RADIUS")
    assert hasattr(ChatWindow, "BASE_BTN_SIZE")
    assert ChatWindow.BASE_FONT == 17


def test_conversation_pane_has_scroll_area():
    """ConversationPane 应包含 QScrollArea。"""
    import inspect
    import ui.chat.window as win_module
    source = inspect.getsource(win_module.ConversationPane)
    assert "QScrollArea" in source
    assert "scroll_to_top" in source


def test_chat_window_width_and_panel_ratio_updated():
    """聊天窗口应更宽，面板高度应缩短到 45%。"""
    import ui.chat.window as win_module

    assert win_module.ChatWindow.BASE_WIDTH == 500
    source = inspect.getsource(win_module.ChatWindow._apply_scale)
    assert "0.45" in source or "0.45)" in source


def test_reload_sprite_uses_lower_visual_anchor():
    """立绘重载目标应更高，以便视觉上整体下沉。"""
    import ui.chat.window as win_module

    source = inspect.getsource(win_module.ChatWindow._reload_sprite)
    assert "0.92" in source or "0.92)" in source


def test_dialog_text_normalization_collapses_extra_blank_lines():
    """显示层应压缩多余空行，但保留段落分隔。"""
    from ui.chat.window import ChatWindow

    raw = "\n\n第一段\n\n\n第二段\n\n\n\n第三段\n\n"
    normalized = ChatWindow._normalize_dialog_text(raw)
    assert normalized == "第一段\n\n第二段\n\n第三段"


def test_dialog_html_uses_tighter_line_height_and_paragraph_gap():
    """HTML 渲染应收紧行高，并用小段距代替整行空白。"""
    from ui.chat.window import ChatWindow

    html = ChatWindow._build_dialog_html("第一段\n\n第二段", font=17, line_height=132, paragraph_gap=4)
    assert "line-height: 132%" in html
    assert "margin:0 0 4px 0;" in html
    assert "<br><br><br>" not in html


def test_rebuild_stylesheet_contains_layered_theme_borders():
    """输入框和按钮样式应包含动态纯玫瑰色主描边。"""
    import ui.chat.window as win_module

    source = inspect.getsource(win_module.ChatWindow._rebuild_stylesheet)
    assert "border: {control_border}px solid #d4567a;" in source
    assert "border-color: #9b3060;" in source


def test_rebuild_stylesheet_keeps_theme_tint_on_top_border():
    """输入框和按钮不应再使用顶光或阴影边。"""
    import ui.chat.window as win_module

    source = inspect.getsource(win_module.ChatWindow._rebuild_stylesheet)
    assert "border-top:" not in source
    assert "border-bottom:" not in source


def test_rebuild_stylesheet_uses_thicker_control_borders():
    """输入框和圆形按钮的主题描边应使用缩放后的 control_border。"""
    import ui.chat.window as win_module

    source = inspect.getsource(win_module.ChatWindow._rebuild_stylesheet)
    assert source.count("border: {control_border}px solid #d4567a;") >= 2


def test_glass_panel_uses_solid_rose_border():
    """对话框外框应使用缩放后的纯玫瑰色描边。"""
    import ui.chat.window as win_module

    panel_source = inspect.getsource(win_module.GlassPanel.paintEvent)
    rebuild_source = inspect.getsource(win_module.ChatWindow._rebuild_stylesheet)
    assert "QColor(self._border_color)" in panel_source
    assert "self._panel.set_border_style(panel_border, \"#d4567a\")" in rebuild_source
    assert "QColor(255, 255, 255, 92)" not in panel_source


def test_chat_window_border_widths_scale_with_minimums():
    """默认边框厚度和缩放下限应固定。"""
    from ui.chat.window import ChatWindow

    assert ChatWindow._scaled_border_widths(1.0) == (3, 2)
    assert ChatWindow._scaled_border_widths(0.5) == (2, 1)
    assert ChatWindow._scaled_border_widths(1.8) == (5, 4)


def test_chat_window_uses_system_font_scale(monkeypatch):
    """聊天正文和输入框应使用系统字体与聊天字号倍率。"""
    _app()
    monkeypatch.setattr("ui.chat.window.LLMManager", _FakeLLMManager)
    monkeypatch.setattr("ui.chat.window.AgentManager", _FakeAgentManager)
    monkeypatch.setattr("ui.chat.window.SpriteManager", _FakeSpriteManager)

    system_config = SystemConfig(font_family="Microsoft YaHei", font_size=16)
    system_config.chat_display.font_scale = 1.25
    window = None
    try:
        from ui.chat.window import ChatWindow

        window = ChatWindow(LLMConfig(), system_config=system_config)
        window._set_dialog_text("测试文本")

        assert "font-size: 20px" in window._dialog_box.text()
        assert "font-family: \"Microsoft YaHei\"" in window._dialog_box.styleSheet()
        assert "font-family: \"Microsoft YaHei\"" in window._input.styleSheet()
    finally:
        if window is not None:
            window.close()


def test_chat_window_apply_system_config_updates_font_and_bubble(monkeypatch):
    """系统设置保存后应能刷新已打开聊天窗的显示参数。"""
    _app()
    monkeypatch.setattr("ui.chat.window.LLMManager", _FakeLLMManager)
    monkeypatch.setattr("ui.chat.window.AgentManager", _FakeAgentManager)
    monkeypatch.setattr("ui.chat.window.SpriteManager", _FakeSpriteManager)

    window = None
    try:
        from ui.chat.window import ChatWindow

        window = ChatWindow(LLMConfig(), system_config=SystemConfig(font_family="Microsoft YaHei", font_size=14))
        config = SystemConfig(font_family="Arial", font_size=18)
        config.chat_display.font_scale = 1.25
        config.chat_display.bubble_scale = 1.2
        config.passive_interaction.bubble_max_width = 360

        window.apply_system_config(config)

        assert window._display_font_family == "Arial"
        assert window._display_font_size == 18
        assert 'font-family: "Arial"' in window._input.styleSheet()
        assert window._passive_bubble.maximumWidth() <= int(360 * 1.2)
    finally:
        if window is not None:
            window.close()


def test_launch_chat_passes_system_and_asr_config(monkeypatch):
    """设置窗启动聊天时应传递系统显示配置和 ASR 配置。"""
    _app()
    captured = {}

    class DummyChatWindow:
        def __init__(self, llm_config, **kwargs):
            captured["llm"] = llm_config
            captured["system"] = kwargs.get("system_config")
            captured["asr"] = kwargs.get("asr_config")

        def show(self):
            return None

        def set_memory_store(self, memory_store):
            return None

    monkeypatch.setattr("ui.settings.window.ChatWindow", DummyChatWindow)
    monkeypatch.setattr("ui.settings.window.PluginHost", lambda *_: SimpleNamespace(load=lambda: None))
    monkeypatch.setattr("ui.settings.window.MCPHost", lambda *_: SimpleNamespace(connect_all=lambda: None))
    monkeypatch.setattr("ui.settings.window.ToolRegistry", lambda **_: SimpleNamespace())

    class DummyLoader:
        def __init__(self, *_args, **_kwargs):
            self.memory_ready = SimpleNamespace(connect=lambda *_: None)
            self.memory_failed = SimpleNamespace(connect=lambda *_: None)

        def start(self):
            return None

    monkeypatch.setattr("ui.settings.window.MemoryLoaderThread", DummyLoader)

    from ui.settings.window import SettingsWindow

    window = SettingsWindow()
    window._config.api.asr = ASRConfig(engine="whisper")
    window._launch_chat()

    assert captured["system"] is window._config.system
    assert captured["asr"] is window._config.api.asr


def test_chat_window_status_bar_exposes_stop_retry_and_logs(monkeypatch):
    _app()
    monkeypatch.setattr("ui.chat.window.LLMManager", _FakeLLMManager)
    monkeypatch.setattr("ui.chat.window.AgentManager", _FakeAgentManager)
    monkeypatch.setattr("ui.chat.window.SpriteManager", _FakeSpriteManager)

    from ui.chat.window import ChatWindow

    window = ChatWindow(LLMConfig(), system_config=SystemConfig())
    try:
        window._last_user_input = "你好"

        window._set_chat_status("正在思考...", busy=True)

        assert not window._status_label.isHidden()
        assert not window._stop_btn.isHidden()
        assert window._send_btn.text() == "×"
        assert "停止当前生成" in window._send_btn.toolTip()

        window._set_chat_status("请求失败：boom", error=True, can_retry=True, show_logs=True)

        assert not window._retry_btn.isHidden()
        assert not window._logs_btn.isHidden()
        assert window._send_btn.text() == ">"
        assert "请求失败" in window._status_label.text()
    finally:
        window.close()


def test_chat_window_stream_display_batches_until_flush(monkeypatch):
    _app()
    monkeypatch.setattr("ui.chat.window.LLMManager", _FakeLLMManager)
    monkeypatch.setattr("ui.chat.window.AgentManager", _FakeAgentManager)
    monkeypatch.setattr("ui.chat.window.SpriteManager", _FakeSpriteManager)

    from ui.chat.window import ChatWindow

    window = ChatWindow(LLMConfig(), system_config=SystemConfig())
    rendered = []
    try:
        monkeypatch.setattr(window, "_set_dialog_text", lambda text: rendered.append(text), raising=False)

        window._queue_dialog_text_update("第一段")
        window._queue_dialog_text_update("第一段第二段")

        assert rendered == []

        window._flush_dialog_text_update()

        assert rendered == ["第一段第二段"]
    finally:
        window.close()
