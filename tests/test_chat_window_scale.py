import inspect


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
    """输入框和按钮样式应包含更明显的主题描边层次。"""
    import ui.chat.window as win_module

    source = inspect.getsource(win_module.ChatWindow._rebuild_stylesheet)
    assert "rgba(212, 86, 122, 0.32)" in source
    assert "rgba(155, 48, 96, 0.18)" in source


def test_rebuild_stylesheet_keeps_theme_tint_on_top_border():
    """输入框和按钮顶边应保留浅粉主题色，而不是纯白。"""
    import ui.chat.window as win_module

    source = inspect.getsource(win_module.ChatWindow._rebuild_stylesheet)
    assert "border-top: 1px solid rgba(255, 214, 224, 0.78);" in source
    assert "border-top: 1px solid rgba(255, 220, 228, 0.8);" in source
