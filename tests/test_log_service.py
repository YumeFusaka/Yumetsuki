from datetime import datetime

from core.log_service import LogService
from core.log_types import LogChannel, LogEvent, LogLevel, build_log_event


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


def test_list_conversation_sessions_returns_latest_first(tmp_path):
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

    assert sessions[0]["session_id"] == "session-2"
    assert sessions[0]["label"]
    assert sessions[1]["session_id"] == "session-1"


def test_list_sources_returns_sorted_unique_sources(tmp_path):
    service = LogService(tmp_path)
    service.record_system("chat.tts", "tts.segment_enqueued", "segment", {}, session_id="s1")
    service.record_system("llm.manager", "llm.stream_started", "stream", {}, session_id="s1")
    service.record_system("chat.tts", "tts.segment_played", "played", {}, session_id="s1")

    assert service.list_sources() == ["chat.tts", "llm.manager"]
