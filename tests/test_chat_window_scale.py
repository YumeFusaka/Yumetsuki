import inspect


def test_panel_height_is_50_percent():
    """对话框 panel 应占窗口高度的 50%。"""
    import ui.chat.window as win_module
    source = inspect.getsource(win_module.ChatWindow._apply_scale)
    assert "0.50" in source or "0.5)" in source, "panel 比例应为 50%"
    assert "0.38" not in source, "旧的 38% 比例应已移除"


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
