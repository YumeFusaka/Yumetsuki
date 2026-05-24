from datetime import datetime

from core.log_service import LogService
from core.log_types import LogChannel, LogEvent, LogLevel


class NoFrontPopList(list):
    def pop(self, index=-1):
        if index == 0:
            raise AssertionError("flush should not drain pending events with pop(0)")
        return super().pop(index)


def test_log_service_writes_system_events_to_daily_jsonl(tmp_path):
    service = LogService(log_root=tmp_path, system_flush_interval_ms=0)
    event = LogEvent(
        id="evt-1",
        timestamp=datetime(2026, 5, 24, 21, 14, 3, 182000),
        channel=LogChannel.SYSTEM,
        level=LogLevel.INFO,
        source="chat.tts",
        event_type="tts.segment_enqueued",
        session_id="s1",
        utterance_id=1,
        summary="segment enqueued",
        details={"text": "你好。"},
        sensitive=False,
    )

    service.record(event)
    service.flush()

    log_file = tmp_path / "system" / "2026-05-24.jsonl"
    assert log_file.exists()
    assert '"event_type": "tts.segment_enqueued"' in log_file.read_text(encoding="utf-8")


def test_log_service_exports_filtered_events_to_jsonl(tmp_path):
    service = LogService(log_root=tmp_path, system_flush_interval_ms=0)
    service.record_system(
        "chat.tts",
        "tts.segment_enqueued",
        "segment enqueued",
        {"segment_id": 1},
        session_id="s1",
    )
    service.record_system(
        "tool.registry",
        "tool.call_completed",
        "tool completed",
        {"tool": "echo"},
        session_id="s1",
    )

    export_path = tmp_path / "export.jsonl"
    service.export_events(export_path, channel="system", source="chat.tts")

    text = export_path.read_text(encoding="utf-8")
    assert "tts.segment_enqueued" in text
    assert "tool.call_completed" not in text


def test_log_service_flushes_immediately_when_interval_is_zero(tmp_path):
    service = LogService(log_root=tmp_path, system_flush_interval_ms=0)

    service.record_system(
        "chat.tts",
        "tts.segment_enqueued",
        "segment enqueued",
        {"segment_id": 1},
        session_id="s1",
    )

    assert any((tmp_path / "system").glob("*.jsonl"))


def test_list_conversation_sessions_returns_latest_first_with_readable_fields(tmp_path):
    service = LogService(tmp_path)
    service.record(
        LogEvent(
            id="evt-session-1",
            timestamp=datetime(2026, 5, 24, 21, 14, 3, 182000),
            channel=LogChannel.CONVERSATION,
            level=LogLevel.INFO,
            source="agent.manager",
            event_type="conversation.user_input",
            session_id="session-1",
            utterance_id=None,
            summary="用户输入: 你好",
            details={"text": "你好"},
            sensitive=False,
        )
    )
    service.record(
        LogEvent(
            id="evt-session-1-latest",
            timestamp=datetime(2026, 5, 24, 21, 16, 3, 182000),
            channel=LogChannel.CONVERSATION,
            level=LogLevel.INFO,
            source="agent.manager",
            event_type="conversation.assistant_output",
            session_id="session-1",
            utterance_id=None,
            summary="助手回复: 这是更晚的一条消息",
            details={"text": "这是更晚的一条消息"},
            sensitive=False,
        )
    )
    service.record(
        LogEvent(
            id="evt-session-2",
            timestamp=datetime(2026, 5, 24, 21, 15, 3, 182000),
            channel=LogChannel.CONVERSATION,
            level=LogLevel.INFO,
            source="agent.manager",
            event_type="conversation.user_input",
            session_id="session-2",
            utterance_id=None,
            summary="用户输入: 下午好",
            details={"text": "下午好"},
            sensitive=False,
        )
    )

    sessions = service.list_conversation_sessions(limit=10)

    assert [session["session_id"] for session in sessions] == ["session-1", "session-2"]
    assert sessions[0]["last_timestamp"] == "2026-05-24T21:16:03.182"
    assert sessions[0]["preview"] == "这是更晚的一条消息"
    assert sessions[0]["label"].startswith("21:16")
    assert sessions[0]["label"].endswith(sessions[0]["preview"])
    assert len(sessions[0]["label"]) > len(sessions[0]["preview"])
    assert sessions[1]["last_timestamp"] == "2026-05-24T21:15:03.182"
    assert sessions[1]["preview"] == "下午好"
    assert sessions[1]["label"].startswith("21:15")
    assert sessions[1]["label"].endswith(sessions[1]["preview"])


def test_list_conversation_sessions_applies_limit_after_sorting(tmp_path):
    service = LogService(tmp_path)
    service.record(
        LogEvent(
            id="evt-session-1",
            timestamp=datetime(2026, 5, 24, 21, 14, 3, 182000),
            channel=LogChannel.CONVERSATION,
            level=LogLevel.INFO,
            source="agent.manager",
            event_type="conversation.user_input",
            session_id="session-1",
            utterance_id=None,
            summary="用户输入: 会被截掉",
            details={"text": "会被截掉"},
            sensitive=False,
        )
    )
    service.record(
        LogEvent(
            id="evt-session-2",
            timestamp=datetime(2026, 5, 24, 21, 15, 3, 182000),
            channel=LogChannel.CONVERSATION,
            level=LogLevel.INFO,
            source="agent.manager",
            event_type="conversation.user_input",
            session_id="session-2",
            utterance_id=None,
            summary="用户输入: 保留第二新",
            details={"text": "保留第二新"},
            sensitive=False,
        )
    )
    service.record(
        LogEvent(
            id="evt-session-3",
            timestamp=datetime(2026, 5, 24, 21, 16, 3, 182000),
            channel=LogChannel.CONVERSATION,
            level=LogLevel.INFO,
            source="agent.manager",
            event_type="conversation.user_input",
            session_id="session-3",
            utterance_id=None,
            summary="用户输入: 保留最新",
            details={"text": "保留最新"},
            sensitive=False,
        )
    )

    sessions = service.list_conversation_sessions(limit=2)

    assert [session["session_id"] for session in sessions] == ["session-3", "session-2"]


def test_log_service_flushes_pending_events_without_front_pop(tmp_path):
    service = LogService(log_root=tmp_path, system_flush_interval_ms=999999)
    service.record_system("chat.tts", "tts.segment_enqueued", "first", {"segment_id": 1}, session_id="s1")
    service.record_system("chat.tts", "tts.segment_played", "second", {"segment_id": 2}, session_id="s1")
    service._pending = NoFrontPopList(service._pending)

    service.flush()

    log_file = tmp_path / "system" / f"{datetime.now():%Y-%m-%d}.jsonl"
    lines = log_file.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert '"summary": "first"' in lines[0]
    assert '"summary": "second"' in lines[1]
    assert service._pending == []


def test_list_sources_returns_sorted_unique_sources(tmp_path):
    service = LogService(tmp_path)
    service.record_system("chat.tts", "tts.segment_enqueued", "segment", {}, session_id="s1")
    service.record_system("llm.manager", "llm.stream_started", "stream", {}, session_id="s1")
    service.record_system("chat.tts", "tts.segment_played", "played", {}, session_id="s1")

    assert service.list_sources() == ["chat.tts", "llm.manager"]
