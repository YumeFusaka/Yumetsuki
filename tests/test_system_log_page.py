from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPalette
from PySide6.QtWidgets import QApplication
from PySide6.QtWidgets import QStyle
from PySide6.QtWidgets import QStyleOptionViewItem

from ui.settings.pages.agent_page import AgentPage
from ui.settings.pages.system_log_page import SOURCE_COLORS
from ui.settings.pages.system_log_page import SOURCE_GROUPS
from ui.settings.pages.system_log_page import SystemLogPage


def _app() -> QApplication:
    app = QApplication.instance()
    return app or QApplication([])


class _FakeLogService:
    log_root = Path(".")

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

    assert page._title.text() == "平台日志"
    assert page._empty_label.text() == "暂无平台日志。"
    assert page._event_list.count() == 0
    assert page._detail_text.isHidden()
    assert not page._refresh_timer.isActive()


def test_system_log_page_export_dialog_uses_platform_log_label(monkeypatch, tmp_path):
    _app()
    page = SystemLogPage(_FakeLogService())
    captured = {}

    def fake_get_save_file_name(parent, title, path, filter_text):
        captured["title"] = title
        captured["path"] = path
        return str(tmp_path / "platform-export.jsonl"), filter_text

    monkeypatch.setattr(
        "ui.settings.pages.system_log_page.QFileDialog.getSaveFileName",
        fake_get_save_file_name,
    )

    assert page._choose_export_path() == tmp_path / "platform-export.jsonl"
    assert captured["title"] == "导出平台日志"
    assert captured["path"].endswith("platform-export.jsonl")


def test_system_log_page_refresh_timer_only_runs_while_visible():
    _app()
    page = SystemLogPage(_FakeLogService())

    assert not page._refresh_timer.isActive()

    page.show()
    QApplication.processEvents()
    assert page._refresh_timer.isActive()

    page.hide()
    QApplication.processEvents()
    assert not page._refresh_timer.isActive()


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
            assert kwargs["source"] is None
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
    page._source_group_filter.setCurrentText("TTS")
    page._source_filter.setCurrentText("chat.tts")
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
        def query_events(self, **kwargs):
            return [
                {
                    "timestamp": "2026-05-24T10:25:39.573",
                    "level": "info",
                    "source": "tool.registry",
                    "session_id": "session-1",
                    "event_type": "tool.call_completed",
                    "summary": "tool completed",
                    "details": {"text": "keep me"},
                },
                {
                    "timestamp": "2026-05-24T10:25:40.221",
                    "level": "error",
                    "source": "llm.manager",
                    "session_id": "session-1",
                    "event_type": "llm.stream_failed",
                    "summary": "llm failed",
                    "details": {"text": "drop me"},
                },
            ]

    page = SystemLogPage(_Service())
    monkeypatch.setattr(page, "_choose_export_path", lambda: tmp_path / "system-export.jsonl", raising=False)
    page._source_group_filter.setCurrentText("工具")
    page._source_filter.setCurrentText("tool.registry")

    page._export_current_view()

    text = (tmp_path / "system-export.jsonl").read_text(encoding="utf-8")
    assert "tool.call_completed" in text
    assert "llm.stream_failed" not in text


def test_system_log_page_export_matches_level_keyword_and_group_filters(monkeypatch, tmp_path):
    _app()

    class _Service:
        def query_events(self, **kwargs):
            return [
                {
                    "timestamp": "2026-05-24T10:25:39.573",
                    "level": "info",
                    "source": "chat.tts",
                    "session_id": "session-1",
                    "event_type": "tts.segment_enqueued",
                    "summary": "segment enqueued",
                    "details": {"text": "目标句子"},
                },
                {
                    "timestamp": "2026-05-24T10:25:40.221",
                    "level": "warn",
                    "source": "chat.tts",
                    "session_id": "session-1",
                    "event_type": "tts.segment_skipped",
                    "summary": "segment skipped",
                    "details": {"text": "目标句子"},
                },
                {
                    "timestamp": "2026-05-24T10:25:41.000",
                    "level": "info",
                    "source": "llm.manager",
                    "session_id": "session-1",
                    "event_type": "llm.stream_progress",
                    "summary": "目标句子 from llm",
                    "details": {},
                },
            ]

    page = SystemLogPage(_Service())
    monkeypatch.setattr(page, "_choose_export_path", lambda: tmp_path / "filtered.jsonl", raising=False)
    page._source_group_filter.setCurrentText("TTS")
    page._level_filter.setCurrentText("INFO")
    page._keyword_filter.setText("目标句子")

    page._export_current_view()

    text = (tmp_path / "filtered.jsonl").read_text(encoding="utf-8")
    assert "tts.segment_enqueued" in text
    assert "tts.segment_skipped" not in text
    assert "llm.stream_progress" not in text


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
    assert "border-left: 1px" not in page.styleSheet()
    assert "QComboBox::down-arrow" in page.styleSheet()
    assert "image: url(" in page.styleSheet()
    assert "border-top: 6px solid #9b3060" not in page.styleSheet()
    assert "border-left: 5px solid transparent" not in page.styleSheet()


def test_system_log_page_toolbar_keeps_keyword_as_only_responsive_field():
    _app()
    page = SystemLogPage(_FakeLogService())

    assert page._keyword_filter.sizePolicy().horizontalStretch() == 1
    assert page._source_filter.sizePolicy().horizontalStretch() == 0
    assert page._source_filter.minimumWidth() >= 150
    assert page._keyword_filter.minimumWidth() >= 220


def test_system_log_page_action_buttons_are_compact_tools():
    _app()
    page = SystemLogPage(_FakeLogService())

    buttons = [page._refresh_btn, page._export_btn, page._open_dir_btn, page._copy_btn]

    assert [button.text() for button in buttons] == ["刷新", "导出", "打开目录", "复制详情"]
    assert all(button.objectName() == "logActionButton" for button in buttons)
    assert all(button.property("settingsFontRole") == "small" for button in buttons)
    assert all(button.minimumHeight() == 28 for button in buttons)
    assert all(button.maximumHeight() <= 34 for button in buttons)
    assert "QPushButton#logActionButton" in page.styleSheet()
    assert "font-size: 12px" in page.styleSheet()
    assert "padding: 5px 10px" in page.styleSheet()


def test_system_log_page_filters_sources_by_group_and_specific_source():
    _app()

    class _Service:
        log_root = "."

        def query_events(self, **kwargs):
            assert kwargs["source"] is None
            return [
                {
                    "timestamp": "2026-05-24T10:25:39.573",
                    "level": "info",
                    "source": "session.manager",
                    "session_id": "session-1",
                    "event_type": "memory.loaded",
                    "summary": "加载记忆",
                    "details": {"text": "memory"},
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
                {
                    "timestamp": "2026-05-24T10:25:41.000",
                    "level": "info",
                    "source": "memory.mem0",
                    "session_id": "session-1",
                    "event_type": "memory.saved",
                    "summary": "写入 mem0",
                    "details": {},
                },
                {
                    "timestamp": "2026-05-24T10:25:42.000",
                    "level": "info",
                    "source": "memory.mem0.cache",
                    "session_id": "session-1",
                    "event_type": "memory.cache_saved",
                    "summary": "不应匹配子串来源",
                    "details": {},
                },
            ]

    page = SystemLogPage(_Service())
    assert [page._source_group_filter.itemText(i) for i in range(page._source_group_filter.count())] == [
        "全部",
        "记忆",
        "LLM",
        "切句",
        "STT",
        "TTS",
        "工具",
        "插件",
        "MCP",
        "UI",
        "Agent",
    ]

    page._source_group_filter.setCurrentText("STT")
    assert [page._source_filter.itemText(i) for i in range(page._source_filter.count())] == [
        "全部",
        "chat.stt",
        "stt.faster_whisper",
    ]

    page._source_group_filter.setCurrentText("记忆")
    assert [page._source_filter.itemText(i) for i in range(page._source_filter.count())] == [
        "全部",
        "session.manager",
        "memory.mem0",
        "memory.ledger",
    ]

    page._refresh_view()
    assert page._event_list.count() == 2

    page._source_group_filter.setCurrentText("全部")
    page._source_filter.addItem("memory.mem0", "memory.mem0")
    page._source_filter.setCurrentText("memory.mem0")
    page._refresh_view()

    assert page._event_list.count() == 1
    assert "写入 mem0" in page._event_list.item(0).text()


def test_system_log_page_continuous_text_view_renders_filtered_plain_text():
    _app()

    class _Service:
        log_root = "."

        def query_events(self, **kwargs):
            return [
                {
                    "timestamp": "2026-05-24T10:25:39.573",
                    "level": "info",
                    "source": "chat.tts",
                    "session_id": "session-1",
                    "event_type": "tts.segment_enqueued",
                    "summary": "segment enqueued",
                    "details": {"text": "第一句"},
                },
                {
                    "timestamp": "2026-05-24T10:25:40.221",
                    "level": "info",
                    "source": "llm.manager",
                    "session_id": "session-1",
                    "event_type": "llm.stream_started",
                    "summary": "开始生成回复",
                    "details": {"text": "不应出现"},
                },
            ]

    page = SystemLogPage(_Service())
    page._source_group_filter.setCurrentText("TTS")
    page._view_mode.setCurrentText("连续文本")
    page._refresh_view()

    assert page._event_list.isHidden()
    assert not page._continuous_text.isHidden()
    assert page._continuous_text.isReadOnly()
    assert page._continuous_text.toPlainText().strip()
    assert "segment enqueued" in page._continuous_text.toPlainText()
    assert "第一句" in page._continuous_text.toPlainText()
    assert "chat.tts" in page._continuous_text.toPlainText()
    assert "llm.manager" not in page._continuous_text.toPlainText()
    assert "开始生成回复" not in page._continuous_text.toPlainText()


def test_system_log_page_continuous_text_view_colors_each_source():
    _app()

    class _Service:
        log_root = "."

        def query_events(self, **kwargs):
            return [
                {
                    "timestamp": "2026-05-24T10:25:39.573",
                    "level": "info",
                    "source": "chat.tts",
                    "session_id": "session-1",
                    "event_type": "tts.segment_enqueued",
                    "summary": "发送 TTS",
                    "details": {"text": "第一句"},
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
    page._view_mode.setCurrentText("连续文本")
    page._refresh_view()

    html = page._continuous_text.toHtml().lower()
    assert SOURCE_COLORS["chat.tts"] in html
    assert SOURCE_COLORS["llm.manager"] in html
    assert page._continuous_text.toPlainText().count("session-1") == 2


def test_system_log_page_refresh_preserves_detail_scroll_when_selected_event_is_unchanged():
    _app()

    repeated_text = "\n".join(f"line {i}" for i in range(200))
    event = {
        "id": "same-event",
        "timestamp": "2026-05-24T10:25:39.573",
        "level": "info",
        "source": "agent.manager",
        "session_id": "session-1",
        "event_type": "conversation.user_input",
        "summary": "用户输入",
        "details": {"text": repeated_text},
    }

    class _Service:
        log_root = "."

        def query_events(self, **kwargs):
            return [event]

    page = SystemLogPage(_Service())
    page._refresh_view()
    page._event_list.setCurrentRow(0)
    detail_bar = page._detail_text.verticalScrollBar()
    detail_bar.setValue(max(1, detail_bar.maximum() // 2))
    previous_value = detail_bar.value()
    previous_text = page._detail_text.toPlainText()

    page._refresh_view()

    assert page._detail_text.toPlainText() == previous_text
    assert detail_bar.value() == previous_value


def test_system_log_page_refreshes_detail_when_selected_event_payload_changes():
    _app()

    repeated_text = "\n".join(f"line {i}" for i in range(200))
    original_event = {
        "id": "same-event",
        "timestamp": "2026-05-24T10:25:39.573",
        "level": "info",
        "source": "agent.manager",
        "session_id": "session-1",
        "event_type": "conversation.user_input",
        "summary": "用户输入",
        "details": {"text": repeated_text, "version": 1},
    }
    updated_event = {
        "id": "same-event",
        "timestamp": "2026-05-24T10:25:39.573",
        "level": "info",
        "source": "agent.manager",
        "session_id": "session-1",
        "event_type": "conversation.user_input",
        "summary": "用户输入",
        "details": {"text": repeated_text, "version": 2, "extra": "changed"},
    }

    class _Service:
        event = original_event

        def query_events(self, **kwargs):
            return [self.event]

    service = _Service()
    page = SystemLogPage(service)
    page._refresh_view()
    page._event_list.setCurrentRow(0)

    detail_bar = page._detail_text.verticalScrollBar()
    detail_bar.setValue(max(1, detail_bar.maximum() // 2))
    previous_value = detail_bar.value()

    service.event = updated_event
    page._refresh_view()

    assert '"version": 2' in page._detail_text.toPlainText()
    assert '"extra": "changed"' in page._detail_text.toPlainText()
    assert detail_bar.value() == previous_value


def test_system_log_page_continuous_text_only_autoscrolls_when_near_bottom():
    _app()

    base_events = [
        {
            "id": f"event-{i}",
            "timestamp": f"2026-05-24T10:25:{i:02d}.000",
            "level": "info",
            "source": "agent.manager",
            "session_id": "session-1",
            "event_type": "conversation.user_input",
            "summary": f"用户输入 {i}",
            "details": {"text": f"text {i}"},
        }
        for i in range(40)
    ]

    class _Service:
        log_root = "."

        def __init__(self):
            self.events = list(base_events)

        def query_events(self, **kwargs):
            return list(self.events)

    service = _Service()
    page = SystemLogPage(service)
    page.resize(640, 320)
    page._view_mode.setCurrentText("连续文本")
    page._refresh_view()

    bar = page._continuous_text.verticalScrollBar()
    bar.setValue(max(0, bar.maximum() // 2))
    preserved_value = bar.value()

    service.events.append(
        {
            "id": "event-40",
            "timestamp": "2026-05-24T10:26:40.000",
            "level": "info",
            "source": "agent.manager",
            "session_id": "session-1",
            "event_type": "conversation.user_input",
            "summary": "用户输入 40",
            "details": {"text": "text 40"},
        }
    )
    page._refresh_view()

    assert bar.value() == preserved_value

    bar.setValue(bar.maximum())
    service.events.append(
        {
            "id": "event-41",
            "timestamp": "2026-05-24T10:26:41.000",
            "level": "info",
            "source": "agent.manager",
            "session_id": "session-1",
            "event_type": "conversation.user_input",
            "summary": "用户输入 41",
            "details": {"text": "text 41"},
        }
    )
    page._refresh_view()

    assert bar.value() == bar.maximum()


def test_system_log_page_structured_list_preserves_scroll_when_reading_old_events():
    _app()

    base_events = [
        {
            "id": f"event-{i}",
            "timestamp": f"2026-05-24T10:25:{i:02d}.000",
            "level": "info",
            "source": "agent.manager",
            "session_id": "session-1",
            "event_type": "conversation.user_input",
            "summary": f"用户输入 {i}",
            "details": {"text": f"text {i}"},
        }
        for i in range(60)
    ]

    class _Service:
        log_root = "."

        def __init__(self):
            self.events = list(base_events)

        def query_events(self, **kwargs):
            return list(self.events)

    service = _Service()
    page = SystemLogPage(service)
    page.resize(640, 320)
    page._refresh_view()
    page._event_list.show()
    QApplication.processEvents()

    bar = page._event_list.verticalScrollBar()
    bar.setValue(max(0, bar.maximum() // 2))
    preserved_value = bar.value()

    service.events.append(
        {
            "id": "event-60",
            "timestamp": "2026-05-24T10:26:00.000",
            "level": "info",
            "source": "agent.manager",
            "session_id": "session-1",
            "event_type": "conversation.user_input",
            "summary": "用户输入 60",
            "details": {"text": "text 60"},
        }
    )
    page._refresh_view()
    QApplication.processEvents()

    assert bar.value() == preserved_value


def test_system_log_page_structured_list_does_not_treat_near_bottom_as_bottom():
    _app()

    base_events = [
        {
            "id": f"event-{i}",
            "timestamp": f"2026-05-24T10:25:{i % 60:02d}.000",
            "level": "info",
            "source": "agent.manager",
            "session_id": "session-1",
            "event_type": "conversation.user_input",
            "summary": f"用户输入 {i}",
            "details": {"text": f"text {i}"},
        }
        for i in range(140)
    ]

    class _Service:
        log_root = "."

        def __init__(self):
            self.events = list(base_events)

        def query_events(self, **kwargs):
            return list(self.events)

    service = _Service()
    page = SystemLogPage(service)
    page.resize(640, 320)
    page.show()
    page._refresh_view()
    QApplication.processEvents()

    bar = page._event_list.verticalScrollBar()
    bar.setValue(max(0, bar.maximum() - 10))
    preserved_value = bar.value()
    assert preserved_value < bar.maximum()

    service.events.append(
        {
            "id": "event-140",
            "timestamp": "2026-05-24T10:26:00.000",
            "level": "info",
            "source": "agent.manager",
            "session_id": "session-1",
            "event_type": "conversation.user_input",
            "summary": "用户输入 140",
            "details": {"text": "text 140"},
        }
    )

    page._refresh_view()
    QApplication.processEvents()

    assert bar.value() == preserved_value
    assert bar.value() < bar.maximum()


def test_system_log_page_refresh_does_not_clear_selected_detail_while_rebuilding_list(monkeypatch):
    _app()

    base_events = [
        {
            "id": f"event-{i}",
            "timestamp": f"2026-05-24T10:25:{i:02d}.000",
            "level": "info",
            "source": "agent.manager",
            "session_id": "session-1",
            "event_type": "conversation.user_input",
            "summary": f"用户输入 {i}",
            "details": {"text": f"text {i}"},
        }
        for i in range(30)
    ]

    class _Service:
        log_root = "."

        def __init__(self):
            self.events = list(base_events)

        def query_events(self, **kwargs):
            return list(self.events)

    service = _Service()
    page = SystemLogPage(service)
    page._refresh_view()
    page._event_list.setCurrentRow(10)
    assert page._selected_event["id"] == "event-10"

    calls = []
    original = page._set_selected_event

    def spy(event):
        calls.append(None if event is None else event.get("id"))
        original(event)

    monkeypatch.setattr(page, "_set_selected_event", spy, raising=False)
    service.events.append(
        {
            "id": "event-30",
            "timestamp": "2026-05-24T10:26:00.000",
            "level": "info",
            "source": "agent.manager",
            "session_id": "session-1",
            "event_type": "conversation.user_input",
            "summary": "用户输入 30",
            "details": {"text": "text 30"},
        }
    )

    page._refresh_view()

    assert None not in calls
    assert page._selected_event["id"] == "event-10"
    assert not page._detail_text.isHidden()


def test_system_log_page_colors_items_by_source():
    _app()

    class _Service:
        log_root = "."

        def query_events(self, **kwargs):
            return [
                {
                    "timestamp": "2026-05-24T10:25:39.573",
                    "level": "info",
                    "source": "llm.manager",
                    "session_id": "session-1",
                    "event_type": "llm.stream_started",
                    "summary": "开始生成回复",
                    "details": {},
                },
                {
                    "timestamp": "2026-05-24T10:25:40.221",
                    "level": "info",
                    "source": "chat.tts",
                    "session_id": "session-1",
                    "event_type": "tts.segment_enqueued",
                    "summary": "发送 TTS",
                    "details": {},
                },
            ]

    page = SystemLogPage(_Service())
    page._refresh_view()

    first_color = page._event_list.item(0).foreground().color().name()
    second_color = page._event_list.item(1).foreground().color().name()
    assert first_color != second_color
    assert first_color == "#5f6fb2"


def test_system_log_page_known_sources_have_unique_colors():
    known_sources = {
        source
        for sources in SOURCE_GROUPS.values()
        for source in sources
        if not source.endswith(".*")
    }
    colors = [SOURCE_COLORS[source] for source in known_sources]

    assert len(colors) == len(set(colors))
    assert SOURCE_COLORS["chat.stt"] != SOURCE_COLORS["stt.faster_whisper"]
    assert SOURCE_COLORS["plugin.*"] != SOURCE_COLORS["mcp.*"]


def test_system_log_page_groups_memory_ledger_source_with_memory_chain():
    assert "memory.ledger" in SOURCE_GROUPS["记忆"]


def test_system_log_page_filters_plugin_and_mcp_prefix_sources():
    _app()

    class _Service:
        log_root = "."

        def query_events(self, **kwargs):
            return [
                {
                    "timestamp": "2026-05-24T10:25:39.573",
                    "level": "info",
                    "source": "plugin.demo",
                    "session_id": "session-1",
                    "event_type": "tool.call_completed",
                    "summary": "插件完成",
                    "details": {},
                },
                {
                    "timestamp": "2026-05-24T10:25:40.573",
                    "level": "info",
                    "source": "mcp.notes",
                    "session_id": "session-1",
                    "event_type": "tool.call_completed",
                    "summary": "MCP 完成",
                    "details": {},
                },
            ]

    page = SystemLogPage(_Service())

    page._source_group_filter.setCurrentText("插件")
    page._refresh_view()
    assert page._event_list.count() == 1
    assert "插件完成" in page._event_list.item(0).text()
    assert page._event_list.item(0).foreground().color().name() == SOURCE_COLORS["plugin.*"]

    page._source_group_filter.setCurrentText("MCP")
    page._refresh_view()
    assert page._event_list.count() == 1
    assert "MCP 完成" in page._event_list.item(0).text()
    assert page._event_list.item(0).foreground().color().name() == SOURCE_COLORS["mcp.*"]

    page._source_group_filter.setCurrentText("工具")
    page._refresh_view()
    assert page._event_list.count() == 2
    text = "\n".join(page._event_list.item(i).text() for i in range(page._event_list.count()))
    assert "插件完成" in text
    assert "MCP 完成" in text


def test_system_log_page_selected_item_keeps_source_foreground_color():
    _app()

    class _Service:
        log_root = "."

        def query_events(self, **kwargs):
            return [
                {
                    "timestamp": "2026-05-24T10:25:39.573",
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
    page._event_list.setCurrentRow(0)

    assert "QListWidget::item:selected" in page.styleSheet()
    assert "QListWidget::item:selected {\n    background" in page.styleSheet()
    assert "color: #4a3040;\n    border" not in page.styleSheet()
    assert page._event_list.currentItem().foreground().color().name() == SOURCE_COLORS["llm.manager"]


def test_system_log_page_selected_item_paints_highlighted_text_with_source_color():
    _app()

    class _Service:
        log_root = "."

        def query_events(self, **kwargs):
            return [
                {
                    "timestamp": "2026-05-24T10:25:39.573",
                    "level": "info",
                    "source": "chat.tts",
                    "session_id": "session-1",
                    "event_type": "tts.segment_enqueued",
                    "summary": "发送 TTS",
                    "details": {},
                },
            ]

    page = SystemLogPage(_Service())
    page._refresh_view()
    page._event_list.setCurrentRow(0)

    option = QStyleOptionViewItem()
    option.state |= QStyle.StateFlag.State_Selected
    index = page._event_list.model().index(0, 0)
    delegate = page._event_list.itemDelegate()
    delegate.initStyleOption(option, index)

    assert index.data(Qt.ItemDataRole.ForegroundRole).color().name() == SOURCE_COLORS["chat.tts"]
    assert option.palette.color(QPalette.ColorRole.Text).name() == SOURCE_COLORS["chat.tts"]
    assert option.palette.color(QPalette.ColorRole.HighlightedText).name() == SOURCE_COLORS["chat.tts"]
