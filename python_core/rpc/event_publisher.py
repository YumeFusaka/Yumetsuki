from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any

from .backpressure import BackpressureConfig, BackpressureController
from .context import RpcContext
from .tasks import TaskRegistry


@dataclass
class PublishedEvent:
    type: str
    request_id: str
    sequence: int
    timestamp_ms: int
    payload: dict[str, Any]
    status: str = "accepted"

    def to_envelope(self, context: RpcContext) -> dict[str, Any]:
        return {
            "kind": "event",
            "type": self.type,
            "protocol_version": context.protocol_version,
            "request_id": context.request_id,
            "trace_id": context.trace_id,
            "parent_trace_id": context.parent_trace_id,
            "session_id": context.session_id,
            "sequence": self.sequence,
            "timestamp_ms": self.timestamp_ms,
            "payload": self.payload,
        }


class RpcEventPublisher:
    def __init__(self, task_registry: TaskRegistry | None = None, config: BackpressureConfig | None = None) -> None:
        self.task_registry = task_registry or TaskRegistry()
        self.backpressure = BackpressureController(config)
        self.events: list[PublishedEvent] = []
        self._subscribers: list = []

    def publish(self, context: RpcContext | None, event_type: str, payload: dict[str, Any], terminal: bool = False, progress: bool = False) -> PublishedEvent:
        if context is None:
            raise ValueError("RpcContext is required")
        sequence = self.task_registry.next_sequence(context.request_id)
        status = self.backpressure.accept(
            context.request_id,
            event_type,
            len(json.dumps(payload, ensure_ascii=False).encode("utf-8")),
            terminal=terminal,
            progress=progress,
        )
        event = PublishedEvent(event_type, context.request_id, sequence, int(time.time() * 1000), payload, status)
        if status in {"accepted", "coalesced"} or terminal:
            self.events.append(event)
            for subscriber in list(self._subscribers):
                subscriber(event)
        return event

    def terminal(self, context: RpcContext, state: str, summary: str, error: dict[str, Any] | None = None) -> PublishedEvent:
        envelope = self.task_registry.publish_terminal_event(context.request_id, state, summary, error)
        event = PublishedEvent(
            type=envelope["type"],
            request_id=context.request_id,
            sequence=envelope["sequence"],
            timestamp_ms=int(time.time() * 1000),
            payload=envelope["payload"],
        )
        self.events.append(event)
        return event

    def subscribe(self, callback):
        self._subscribers.append(callback)

        def unsubscribe() -> None:
            if callback in self._subscribers:
                self._subscribers.remove(callback)

        return unsubscribe
