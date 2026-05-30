from PySide6.QtWidgets import QApplication
from types import SimpleNamespace
from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QTextCursor

from config.schema import SystemConfig
from ui.settings.pages.conversation_log_page import ConversationLogPage


def _app() -> QApplication:
    app = QApplication.instance()
    return app or QApplication([])


class _FakeLogService:
    def query_events(self, **kwargs):
        return []

    def list_conversation_sessions(self, limit=20):
        return []


def test_conversation_log_page_builds_readonly_timeline():
    _app()
    page = ConversationLogPage(_FakeLogService())

    assert page._timeline.isReadOnly()
    assert not page._refresh_timer.isActive()


def test_conversation_log_page_refresh_timer_only_runs_while_visible():
    _app()
    page = ConversationLogPage(_FakeLogService())

    assert not page._refresh_timer.isActive()

    page.show()
    QApplication.processEvents()
    assert page._refresh_timer.isActive()

    page.hide()
    QApplication.processEvents()
    assert not page._refresh_timer.isActive()


def test_conversation_log_page_refreshes_current_session_events():
    _app()

    class _Service:
        def query_events(self, **kwargs):
            assert kwargs["channel"] == "conversation"
            assert kwargs["session_id"] == "session-1"
            return [{"summary": "用户：你好", "event_type": "conversation.user_input"}]

    page = ConversationLogPage(_Service())
    page._current_session_id = "session-1"
    page._refresh_view()

    assert "用户：你好" in page._timeline.toPlainText()


def test_conversation_log_page_without_session_id_shows_all_conversation_events():
    _app()

    class _Service:
        def query_events(self, **kwargs):
            assert kwargs["channel"] == "conversation"
            assert kwargs["session_id"] is None
            return [
                {"summary": "用户：你好", "event_type": "conversation.user_input"},
                {"summary": "助手：你好呀", "event_type": "conversation.assistant_reply"},
            ]

    page = ConversationLogPage(_Service())
    page._refresh_view()

    text = page._timeline.toPlainText()
    assert "用户：你好" in text
    assert "助手：你好呀" in text


def test_conversation_log_page_loads_recent_session_labels_from_log_service():
    _app()

    class _Service:
        def __init__(self):
            self.session_limit = None

        def list_conversation_sessions(self, limit=20):
            self.session_limit = limit
            return [
                {"session_id": "session-2", "label": "10:30  最近的回复"},
                {"session_id": "session-1", "label": "09:15  早些的回复"},
            ]

        def query_events(self, **kwargs):
            return []

    service = _Service()
    page = ConversationLogPage(service)

    assert service.session_limit == 20
    assert page._session_selector.itemText(0) == "10:30  最近的回复"
    assert page._session_selector.itemData(0) == "session-2"
    assert page._session_selector.itemText(1) == "09:15  早些的回复"
    assert page._session_selector.itemData(1) == "session-1"


def test_conversation_log_page_initial_current_scope_uses_selected_recent_session():
    _app()

    class _Service:
        def __init__(self):
            self.queries = []

        def list_conversation_sessions(self, limit=20):
            return [{"session_id": "session-2", "label": "10:30  最近的回复"}]

        def query_events(self, **kwargs):
            self.queries.append(kwargs)
            return []

    service = _Service()
    page = ConversationLogPage(service)
    page._refresh_view()

    assert page._scope_selector.currentText() == "当前会话"
    assert page._session_selector.currentData() == "session-2"
    assert service.queries[-1]["session_id"] == "session-2"


def test_conversation_log_page_refresh_preserves_current_session_without_logs():
    _app()

    class _Service:
        def __init__(self):
            self.queries = []

        def list_conversation_sessions(self, limit=20):
            return [{"session_id": "older-session", "label": "09:15  旧会话"}]

        def query_events(self, **kwargs):
            self.queries.append(kwargs)
            return []

    service = _Service()
    page = ConversationLogPage(service)

    page.set_session_id("new-session")
    page._refresh_sessions_and_view()

    assert page._scope_selector.currentText() == "当前会话"
    assert page._current_session_id == "new-session"
    assert page._session_selector.currentData() == "new-session"
    assert service.queries[-1]["session_id"] == "new-session"


def test_conversation_log_page_switches_between_current_and_all_sessions():
    _app()

    class _Service:
        def __init__(self):
            self.queries = []

        def list_conversation_sessions(self, limit=20):
            return [{"session_id": "session-1", "label": "10:30  当前会话"}]

        def query_events(self, **kwargs):
            self.queries.append(kwargs)
            return []

    service = _Service()
    page = ConversationLogPage(service)
    page.set_session_id("session-1")

    assert service.queries[-1]["session_id"] == "session-1"

    page._scope_selector.setCurrentText("全部会话")
    page._refresh_view()
    assert service.queries[-1]["session_id"] is None

    page._scope_selector.setCurrentText("当前会话")
    page._refresh_view()
    assert service.queries[-1]["session_id"] == "session-1"


def test_conversation_log_page_renders_reply_tags_for_time_emotion_tool_and_memory():
    _app()

    class _Service:
        def query_events(self, **kwargs):
            return [
                {
                    "timestamp": "2026-05-24T10:25:39.573",
                    "event_type": "conversation.user_input",
                    "summary": "用户输入",
                    "details": {"text": "哥哥下午好"},
                },
                {
                    "timestamp": "2026-05-24T10:25:48.227",
                    "event_type": "conversation.assistant_reply",
                    "summary": "角色回复",
                    "details": {
                        "text": "诶嘿~ 哥哥下午好呀！",
                        "emotion": "happy",
                        "tool_names": ["web_search"],
                        "memory_count": 1,
                    },
                },
            ]

    page = ConversationLogPage(_Service())
    page._refresh_view()

    text = page._timeline.toPlainText()
    assert "哥哥下午好" in text
    assert "诶嘿~ 哥哥下午好呀！" in text
    assert "happy" in text
    assert "web_search" in text
    assert "关联记忆 1 条" in text
    assert "10:25" in text


def test_conversation_log_page_uses_same_card_structure_for_user_and_assistant_and_inlines_emotion():
    _app()

    class _Service:
        def query_events(self, **kwargs):
            return [
                {
                    "timestamp": "2026-05-24T10:25:39.573",
                    "event_type": "conversation.user_input",
                    "summary": "用户输入",
                    "details": {"text": "哥哥下午好"},
                },
                {
                    "timestamp": "2026-05-24T10:25:48.227",
                    "event_type": "conversation.assistant_reply",
                    "summary": "角色回复",
                    "details": {
                        "text": "诶嘿~ 哥哥下午好呀！",
                        "emotion": "happy",
                        "tool_names": [],
                        "memory_count": 0,
                    },
                },
            ]

    page = ConversationLogPage(_Service())
    page._refresh_view()

    html = page._timeline.toHtml()
    assert "你 · 10:25" in html
    assert "梦月 · 10:25" in html
    assert "诶嘿~ 哥哥下午好呀！" in html
    assert ">happy</span>" in html
    assert "情绪 happy" not in page._timeline.toPlainText()


def test_conversation_log_page_renders_metadata_strip_below_message_body():
    _app()

    page = ConversationLogPage(_FakeLogService())
    html = page._render_message_card(
        speaker="梦月",
        timestamp="19:14",
        text="搜索魔仓杏铃",
        inline_suffix="",
        tags=["工具 system_control__open_browser", "关联记忆 20 条"],
        title_color="#9b3060",
    )

    assert html.index("搜索魔仓杏铃") < html.index("工具 system_control__open_browser")
    assert "border-top" in html


def test_conversation_log_page_renders_wider_rounded_inline_emotion_chip():
    _app()

    class _Service:
        def query_events(self, **kwargs):
            return [
                {
                    "event_type": "conversation.assistant_reply",
                    "summary": "角色回复",
                    "details": {"text": "你好呀", "emotion": "happy"},
                },
            ]

        def list_conversation_sessions(self, limit=20):
            return []

    page = ConversationLogPage(_Service())
    page._refresh_view()

    html = page._render_event_block(
        {
            "event_type": "conversation.assistant_reply",
            "summary": "角色回复",
            "details": {"text": "你好呀", "emotion": "happy"},
        }
    )
    assert "padding: 4px 12px" in html
    assert "border-radius: 999px" in html


def test_conversation_log_page_refresh_appearance_rerenders_html_with_settings_tokens():
    _app()

    class _Service:
        def query_events(self, **kwargs):
            return [
                {
                    "event_type": "conversation.assistant_reply",
                    "summary": "角色回复",
                    "details": {"text": "你好呀", "emotion": "happy"},
                },
            ]

        def list_conversation_sessions(self, limit=20):
            return []

    parent = QWidget()
    parent._config = SimpleNamespace(system=SystemConfig(font_size=24))
    page = ConversationLogPage(_Service(), parent=parent)
    captured = []
    page._timeline.setHtml = lambda html: captured.append(html)

    page.refresh_appearance()
    parent._config.system.font_size = 12
    page.refresh_appearance()

    assert "font-size: 16px" in captured[0]
    assert "font-size: 12px" in captured[-1]


def test_conversation_log_page_auto_refresh_preserves_scroll_when_reading_old_messages():
    _app()

    base_events = [
        {
            "timestamp": f"2026-05-24T10:{i // 60:02d}:{i % 60:02d}.000",
            "event_type": "conversation.user_input" if i % 2 == 0 else "conversation.assistant_reply",
            "summary": f"消息 {i}",
            "details": {"text": "这是一条比较长的对话日志内容 " * 4 + str(i)},
        }
        for i in range(80)
    ]

    class _Service:
        def __init__(self):
            self.events = list(base_events)

        def query_events(self, **kwargs):
            return list(self.events)

        def list_conversation_sessions(self, limit=20):
            return []

    service = _Service()
    page = ConversationLogPage(service)
    page.resize(640, 320)
    page.show()
    page._refresh_view()
    QApplication.processEvents()

    bar = page._timeline.verticalScrollBar()
    bar.setValue(max(0, bar.maximum() // 2))
    preserved_value = bar.value()

    service.events.append(
        {
            "timestamp": "2026-05-24T11:30:00.000",
            "event_type": "conversation.assistant_reply",
            "summary": "新消息",
            "details": {"text": "新追加的日志内容"},
        }
    )
    page._refresh_view()
    QApplication.processEvents()

    assert bar.value() == preserved_value


def test_conversation_log_page_auto_refresh_skips_while_text_is_selected():
    _app()
    calls = []

    class _Service:
        def query_events(self, **kwargs):
            calls.append(kwargs)
            return [
                {
                    "timestamp": "2026-05-24T10:25:39.573",
                    "event_type": "conversation.user_input",
                    "summary": "用户输入",
                    "details": {"text": "这是一条对话日志"},
                }
            ]

        def list_conversation_sessions(self, limit=20):
            return []

    page = ConversationLogPage(_Service())
    page._refresh_view()
    before = len(calls)
    cursor = page._timeline.textCursor()
    cursor.setPosition(0)
    cursor.setPosition(5, QTextCursor.MoveMode.KeepAnchor)
    page._timeline.setTextCursor(cursor)

    page._refresh_if_enabled()

    assert len(calls) == before
