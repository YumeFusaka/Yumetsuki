from PySide6.QtWidgets import QApplication

from ui.settings.pages.agent_page import AgentPage
from ui.settings.pages.system_log_page import SystemLogPage


def _app() -> QApplication:
    app = QApplication.instance()
    return app or QApplication([])


class _FakeLogService:
    def query_events(self, **kwargs):
        return []


def test_agent_page_tabs_no_longer_include_runtime_log():
    _app()
    page = AgentPage()
    labels = [page._tabs.tabText(i) for i in range(page._tabs.count())]

    assert "运行日志" not in labels
    assert labels == ["规划", "反思", "多步推理", "主动行为"]


def test_system_log_page_builds_readonly_log_text():
    _app()
    page = SystemLogPage(_FakeLogService())

    assert page._event_list.count() == 0
    assert page._detail_text.isHidden()


def test_system_log_page_can_copy_selected_event_json(monkeypatch):
    _app()
    page = SystemLogPage(_FakeLogService())
    captured = {}
    monkeypatch.setattr(
        page,
        "_copy_text",
        lambda text: captured.setdefault("text", text),
        raising=False,
    )

    page._set_selected_event(
        {
            "event_type": "tts.segment_enqueued",
            "summary": "segment enqueued",
            "details": {"segment_id": 1},
        }
    )
    page._copy_selected_event_json()

    assert '"tts.segment_enqueued"' in captured["text"]


def test_system_log_page_refreshes_filtered_events():
    _app()

    class _Service:
        def query_events(self, **kwargs):
            assert kwargs.get("channel") is None
            assert kwargs["source"] == "chat.tts"
            return [
                {
                    "timestamp": "2026-05-24T10:25:39.573",
                    "level": "info",
                    "source": "agent.manager",
                    "session_id": "session-1",
                    "event_type": "conversation.user_input",
                    "summary": "用户输入",
                    "details": {"text": "哥哥下午好"},
                },
                {
                    "timestamp": "2026-05-24T10:25:40.221",
                    "level": "info",
                    "event_type": "tts.segment_enqueued",
                    "source": "chat.tts",
                    "summary": "segment enqueued",
                    "session_id": "session-1",
                    "details": {"segment_id": 1},
                }
            ]

    page = SystemLogPage(_Service())
    page._source_filter.setText("chat.tts")
    page._refresh_view()

    assert page._event_list.count() == 1
    assert "segment enqueued" in page._event_list.item(0).text()
    assert "10:25:40.221" in page._event_list.item(0).text()
    assert "chat.tts" in page._event_list.item(0).text()
    page._event_list.setCurrentRow(0)
    assert not page._detail_text.isHidden()
    assert '"segment_id": 1' in page._detail_text.toPlainText()


def test_system_log_page_timeline_can_include_conversation_and_system_events():
    _app()

    class _Service:
        def query_events(self, **kwargs):
            return [
                {
                    "timestamp": "2026-05-24T10:25:39.573",
                    "level": "info",
                    "source": "agent.manager",
                    "session_id": "session-1",
                    "event_type": "conversation.user_input",
                    "summary": "用户输入",
                    "details": {"text": "哥哥下午好"},
                },
                {
                    "timestamp": "2026-05-24T10:25:40.221",
                    "level": "info",
                    "source": "llm.manager",
                    "session_id": "session-1",
                    "event_type": "llm.stream_started",
                    "summary": "开始生成回复",
                    "details": {},
                },
            ]

    page = SystemLogPage(_Service())
    page._refresh_view()

    text = "\n".join(page._event_list.item(i).text() for i in range(page._event_list.count()))
    assert "哥哥下午好" in text
    assert "开始生成回复" in text


def test_system_log_page_detail_stays_hidden_until_event_selected():
    _app()

    class _Service:
        def query_events(self, **kwargs):
            return [
                {
                    "timestamp": "2026-05-24T10:25:39.573",
                    "level": "info",
                    "source": "agent.manager",
                    "session_id": "session-1",
                    "event_type": "conversation.user_input",
                    "summary": "用户输入",
                    "details": {"text": "哥哥下午好"},
                }
            ]

    page = SystemLogPage(_Service())
    page._refresh_view()

    assert page._detail_text.isHidden()
    page._event_list.setCurrentRow(0)
    assert not page._detail_text.isHidden()


def test_system_log_page_keeps_selected_detail_visible_after_refresh():
    _app()

    class _Service:
        def query_events(self, **kwargs):
            return [
                {
                    "timestamp": "2026-05-24T10:25:39.573",
                    "level": "info",
                    "source": "agent.manager",
                    "session_id": "session-1",
                    "event_type": "conversation.user_input",
                    "summary": "用户输入",
                    "details": {"text": "哥哥下午好"},
                }
            ]

    page = SystemLogPage(_Service())
    page._refresh_view()
    page._event_list.setCurrentRow(0)

    page._refresh_view()

    assert not page._detail_text.isHidden()
    assert "哥哥下午好" in page._detail_text.toPlainText()


def test_system_log_page_exports_filtered_events(monkeypatch, tmp_path):
    _app()

    class _Service:
        def export_events(self, path, **kwargs):
            captured["path"] = path
            captured["kwargs"] = kwargs

        def query_events(self, **kwargs):
            return []

    captured = {}
    page = SystemLogPage(_Service())
    monkeypatch.setattr(page, "_choose_export_path", lambda: tmp_path / "system-export.jsonl", raising=False)
    page._source_filter.setText("tool.registry")

    page._export_current_view()

    assert captured["path"] == tmp_path / "system-export.jsonl"
    assert captured["kwargs"]["source"] == "tool.registry"


def test_system_log_page_opens_system_log_directory(monkeypatch, tmp_path):
    _app()

    class _Service:
        def __init__(self, root):
            self.log_root = root

        def query_events(self, **kwargs):
            return []

    page = SystemLogPage(_Service(tmp_path))
    opened = {}
    monkeypatch.setattr(page, "_open_path", lambda path: opened.setdefault("path", path), raising=False)

    page._open_log_directory()

    assert opened["path"] == tmp_path / "system"


def test_system_log_page_styles_combo_and_checkbox_like_theme():
    _app()
    page = SystemLogPage(_FakeLogService())

    assert "QComboBox::drop-down" in page.styleSheet()
    assert "QCheckBox::indicator" in page.styleSheet()
    assert "background: transparent" in page.styleSheet()
