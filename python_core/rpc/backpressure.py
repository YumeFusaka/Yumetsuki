from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BackpressureConfig:
    per_request_max_events: int = 512
    per_request_max_bytes: int = 8 * 1024 * 1024
    global_max_events: int = 5000
    global_max_bytes: int = 32 * 1024 * 1024
    delta_flush_ms: int = 50
    slow_consumer_ms: int = 2000

    @classmethod
    def with_overrides(cls, **overrides: int) -> "BackpressureConfig":
        values = cls().__dict__ | overrides
        return cls(**values)
