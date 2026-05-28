from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import uuid4


class LogChannel(str, Enum):
    CONVERSATION = "conversation"
    SYSTEM = "system"


class LogLevel(str, Enum):
    DEBUG = "debug"
    INFO = "info"
    WARN = "warn"
    ERROR = "error"


@dataclass(frozen=True)
class LogEvent:
    id: str
    timestamp: datetime
    channel: LogChannel
    level: LogLevel
    source: str
    event_type: str
    session_id: str
    utterance_id: int | None
    summary: str
    details: dict[str, Any]
    sensitive: bool = False
    trace_id: str = ""
    request_id: str = ""
    stage: str = ""

    def to_json_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["timestamp"] = self.timestamp.isoformat(timespec="milliseconds")
        data["channel"] = self.channel.value
        data["level"] = self.level.value
        return data


def build_log_event(
    channel: LogChannel,
    level: LogLevel,
    source: str,
    event_type: str,
    session_id: str,
    summary: str,
    details: dict[str, Any] | None = None,
    utterance_id: int | None = None,
    sensitive: bool = False,
    trace_id: str = "",
    request_id: str = "",
    stage: str = "",
) -> LogEvent:
    return LogEvent(
        id=uuid4().hex,
        timestamp=datetime.now(),
        channel=channel,
        level=level,
        source=source,
        event_type=event_type,
        session_id=session_id,
        utterance_id=utterance_id,
        summary=summary,
        details=details or {},
        sensitive=sensitive,
        trace_id=trace_id,
        request_id=request_id,
        stage=stage,
    )
