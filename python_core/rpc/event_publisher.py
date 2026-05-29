from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
import json
import time
from typing import Any, Callable, Deque

from .backpressure import BackpressureConfig
from .context import RpcContext


class EventPublisherError(ValueError):
    pass


@dataclass(frozen=True)
class PublishedEvent:
    payload: dict[str, Any]
    byte_size: int


class RpcEventPublisher:
    def __init__(
        self,
        config: BackpressureConfig | None = None,
        on_event: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        self.config = config or BackpressureConfig()
        self._on_event = on_event
        self._sequence_by_request: dict[str, int] = defaultdict(int)
        self._queue: Deque[PublishedEvent] = deque()
        self._bytes_by_request: dict[str, int] = defaultdict(int)
        self._count_by_request: dict[str, int] = defaultdict(int)
        self._global_bytes = 0
        self._subscriptions: list[Callable[[dict[str, Any]], None]] = []

    def publish(self, event_type: str, context: RpcContext, payload: dict[str, Any]) -> dict[str, Any]:
        if context is None:
            raise EventPublisherError("RpcContext is required")
        self._sequence_by_request[context.request_id] += 1
        event = {
            "kind": "event",
            "type": event_type,
            "request_id": context.request_id,
            "protocol_version": 1,
            "trace_id": context.trace_id,
            "parent_trace_id": context.parent_trace_id,
            "session_id": context.session_id,
            "sequence": self._sequence_by_request[context.request_id],
            "timestamp_ms": int(time.time() * 1000),
            "payload": payload,
        }
        self._enqueue(event)
        if self._on_event is not None:
            self._on_event(event)
        for callback in list(self._subscriptions):
            callback(event)
        return event

    def subscribe(self, callback: Callable[[dict[str, Any]], None]) -> Callable[[], None]:
        self._subscriptions.append(callback)

        def unsubscribe() -> None:
            if callback in self._subscriptions:
                self._subscriptions.remove(callback)

        return unsubscribe

    def drain(self) -> list[dict[str, Any]]:
        events = [item.payload for item in self._queue]
        self._queue.clear()
        self._bytes_by_request.clear()
        self._count_by_request.clear()
        self._global_bytes = 0
        return events

    def last_sequence(self, request_id: str) -> int:
        return self._sequence_by_request.get(request_id, 0)

    def _enqueue(self, event: dict[str, Any]) -> None:
        size = len(json.dumps(event, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
        request_id = event["request_id"]
        terminal = event["payload"].get("terminal_state") in ("done", "error", "cancelled")
        over_request = (
            self._count_by_request[request_id] >= self.config.per_request_max_events
            or self._bytes_by_request[request_id] + size > self.config.per_request_max_bytes
        )
        over_global = (
            len(self._queue) >= self.config.global_max_events
            or self._global_bytes + size > self.config.global_max_bytes
        )
        if (over_request or over_global) and not terminal:
            self._drop_one_non_terminal(request_id)
        self._queue.append(PublishedEvent(payload=event, byte_size=size))
        self._count_by_request[request_id] += 1
        self._bytes_by_request[request_id] += size
        self._global_bytes += size

    def _drop_one_non_terminal(self, preferred_request_id: str) -> None:
        for item in list(self._queue):
            if item.payload["payload"].get("terminal_state") in ("done", "error", "cancelled"):
                continue
            if item.payload["request_id"] == preferred_request_id or len(self._queue) >= self.config.global_max_events:
                self._queue.remove(item)
                request_id = item.payload["request_id"]
                self._count_by_request[request_id] = max(0, self._count_by_request[request_id] - 1)
                self._bytes_by_request[request_id] = max(0, self._bytes_by_request[request_id] - item.byte_size)
                self._global_bytes = max(0, self._global_bytes - item.byte_size)
                return
