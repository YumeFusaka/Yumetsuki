from __future__ import annotations

import json
from pathlib import Path
import time

from core.log_sanitizer import sanitize_details
from core.log_types import LogChannel, LogEvent, LogLevel, build_log_event


class LogService:
    def __init__(self, log_root: Path | str, system_flush_interval_ms: int = 200):
        self._root = Path(log_root)
        self._system_flush_interval_ms = system_flush_interval_ms
        self._pending: list[LogEvent] = []
        self._events: list[LogEvent] = []
        self._last_flush_monotonic = time.monotonic()

    @property
    def log_root(self) -> Path:
        return self._root

    def record(self, event: LogEvent) -> None:
        sanitized = LogEvent(
            **{**event.__dict__, "details": sanitize_details(event.details)}
        )
        self._pending.append(sanitized)
        self._events.append(sanitized)
        self._flush_if_due()

    def record_system(
        self,
        source: str,
        event_type: str,
        summary: str,
        details: dict,
        session_id: str = "default-session",
        level: LogLevel = LogLevel.INFO,
        utterance_id: int | None = None,
    ) -> None:
        self.record(
            build_log_event(
                channel=LogChannel.SYSTEM,
                level=level,
                source=source,
                event_type=event_type,
                session_id=session_id,
                utterance_id=utterance_id,
                summary=summary,
                details=details,
            )
        )

    def query_events(self, channel=None, source=None, session_id=None) -> list[dict]:
        events = self._events
        if channel is not None:
            channel_value = channel.value if isinstance(channel, LogChannel) else str(channel)
            events = [event for event in events if event.channel.value == channel_value]
        if source is not None:
            events = [event for event in events if event.source == source]
        if session_id is not None:
            events = [event for event in events if event.session_id == session_id]
        return [event.to_json_dict() for event in events]

    def list_sources(self, channel=None) -> list[str]:
        events = self.query_events(channel=channel)
        return sorted({str(event.get("source", "")) for event in events if event.get("source")})

    def list_conversation_sessions(self, limit: int = 20) -> list[dict]:
        grouped: dict[str, dict] = {}
        for event in self.query_events(channel=LogChannel.CONVERSATION):
            session_id = event.get("session_id")
            if not session_id:
                continue
            current = grouped.get(session_id)
            if current is None or event.get("timestamp", "") > current.get("last_timestamp", ""):
                text = (event.get("details") or {}).get("text") or event.get("summary", "")
                grouped[session_id] = {
                    "session_id": session_id,
                    "last_timestamp": event.get("timestamp", ""),
                    "preview": str(text)[:24],
                }
        sessions = sorted(grouped.values(), key=lambda item: item["last_timestamp"], reverse=True)
        for item in sessions:
            item["label"] = f'{item["last_timestamp"][11:16]}  {item["preview"]}'
        return sessions[:limit]

    def export_events(self, path: Path | str, channel=None, source=None, session_id=None) -> None:
        export_path = Path(path)
        export_path.parent.mkdir(parents=True, exist_ok=True)
        events = self.query_events(channel=channel, source=source, session_id=session_id)
        with export_path.open("w", encoding="utf-8") as fh:
            for event in events:
                fh.write(json.dumps(event, ensure_ascii=False) + "\n")

    def flush(self) -> None:
        while self._pending:
            event = self._pending.pop(0)
            folder = "system" if event.channel == LogChannel.SYSTEM else "conversation"
            filename = (
                f"{event.timestamp:%Y-%m-%d}.jsonl"
                if event.channel == LogChannel.SYSTEM
                else f"{event.session_id}.jsonl"
            )
            path = self._root / folder / filename
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(event.to_json_dict(), ensure_ascii=False) + "\n")
        self._last_flush_monotonic = time.monotonic()

    def _flush_if_due(self) -> None:
        if self._system_flush_interval_ms <= 0:
            self.flush()
            return
        elapsed_ms = (time.monotonic() - self._last_flush_monotonic) * 1000
        if elapsed_ms >= self._system_flush_interval_ms:
            self.flush()
