from __future__ import annotations

from python_core.rpc.backpressure import BackpressureConfig, BackpressureController


def test_default_request_backpressure_limit() -> None:
    controller = BackpressureController(BackpressureConfig(per_request_max_events=2))
    assert controller.accept("req", "chat.delta", 1) == "accepted"
    assert controller.accept("req", "chat.delta", 1) == "accepted"
    assert controller.accept("req", "chat.delta", 1) == "request_backpressure"


def test_global_backpressure_limit() -> None:
    controller = BackpressureController(BackpressureConfig(global_max_events=1))
    assert controller.accept("req1", "chat.delta", 1) == "accepted"
    assert controller.accept("req2", "chat.delta", 1) == "global_degraded"


def test_progress_events_are_coalesced_and_terminal_events_are_accepted() -> None:
    controller = BackpressureController(BackpressureConfig(per_request_max_events=0, global_max_events=0))
    assert controller.accept("req", "diagnostics.progress", 1, progress=True) == "coalesced"
    assert controller.accept("req", "chat.done", 999999, terminal=True) == "accepted"


def test_slow_consumer_summary() -> None:
    controller = BackpressureController(BackpressureConfig(slow_consumer_seconds=2.0))
    assert controller.slow_consumer_summary(1.0) is None
    assert controller.slow_consumer_summary(2.1)["type"] == "backpressure.summary"
