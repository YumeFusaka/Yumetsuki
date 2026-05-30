from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BackpressureConfig:
    per_request_max_events: int = 512
    per_request_max_bytes: int = 8 * 1024 * 1024
    global_max_events: int = 5000
    global_max_bytes: int = 32 * 1024 * 1024
    text_delta_coalesce_ms_min: int = 30
    text_delta_coalesce_ms_max: int = 80
    slow_consumer_seconds: float = 2.0


class BackpressureController:
    def __init__(self, config: BackpressureConfig | None = None) -> None:
        self.config = config or BackpressureConfig()
        self._request_counts: dict[str, int] = {}
        self._request_bytes: dict[str, int] = {}
        self._global_count = 0
        self._global_bytes = 0
        self._latest_progress: dict[tuple[str, str], dict] = {}

    def accept(self, request_id: str, event_type: str, payload_size: int, terminal: bool = False, progress: bool = False) -> str:
        if terminal:
            return "accepted"
        if progress:
            self._latest_progress[(request_id, event_type)] = {"request_id": request_id, "event_type": event_type}
            return "coalesced"

        request_count = self._request_counts.get(request_id, 0) + 1
        request_bytes = self._request_bytes.get(request_id, 0) + payload_size
        global_count = self._global_count + 1
        global_bytes = self._global_bytes + payload_size
        if request_count > self.config.per_request_max_events or request_bytes > self.config.per_request_max_bytes:
            return "request_backpressure"
        if global_count > self.config.global_max_events or global_bytes > self.config.global_max_bytes:
            return "global_degraded"

        self._request_counts[request_id] = request_count
        self._request_bytes[request_id] = request_bytes
        self._global_count = global_count
        self._global_bytes = global_bytes
        return "accepted"

    def slow_consumer_summary(self, seconds_since_consume: float) -> dict | None:
        if seconds_since_consume < self.config.slow_consumer_seconds:
            return None
        return {"type": "backpressure.summary", "message": "consumer is slow"}
