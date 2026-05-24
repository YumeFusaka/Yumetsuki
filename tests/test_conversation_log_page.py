from PySide6.QtWidgets import QApplication

from ui.settings.pages.conversation_log_page import ConversationLogPage


def _app() -> QApplication:
    app = QApplication.instance()
    return app or QApplication([])


class _FakeLogService:
    def query_events(self, **kwargs):
        return []


def test_conversation_log_page_builds_readonly_timeline():
    _app()
    page = ConversationLogPage(_FakeLogService())

    assert page._timeline.isReadOnly()


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
    assert "记忆 1" in text
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
