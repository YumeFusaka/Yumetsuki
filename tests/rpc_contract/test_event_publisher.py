from __future__ import annotations

import pytest

from python_core.rpc.backpressure import BackpressureConfig
from python_core.rpc.context import RpcContext
from python_core.rpc.event_publisher import EventPublisherError, RpcEventPublisher


def context(request_id: str = "req_evt") -> RpcContext:
    return RpcContext(
        request_id=request_id,
        trace_id="trace_evt",
        parent_trace_id=None,
        session_id="sess_evt",
        deadline_ms=30000,
    )


def test_event_publisher_requires_context_and_sequences_per_request() -> None:
    publisher = RpcEventPublisher()
    first = publisher.publish("chat.delta", context(), {"text": "a"})
    second = publisher.publish("chat.delta", context(), {"text": "b"})
    assert first["sequence"] == 1
    assert second["sequence"] == 2
    with pytest.raises(EventPublisherError):
        publisher.publish("chat.delta", None, {"text": "x"})  # type: ignore[arg-type]


def test_backpressure_keeps_terminal_events() -> None:
    publisher = RpcEventPublisher(BackpressureConfig.with_overrides(per_request_max_events=1, global_max_events=2))
    publisher.publish("chat.delta", context(), {"text": "a"})
    publisher.publish("chat.delta", context(), {"text": "b"})
    publisher.publish("chat.done", context(), {"terminal_state": "done", "summary": {}})
    events = publisher.drain()
    assert events[-1]["type"] == "chat.done"
    assert len(events) <= 2


def test_subscribe_and_unsubscribe() -> None:
    seen: list[str] = []
    publisher = RpcEventPublisher()
    unsubscribe = publisher.subscribe(lambda event: seen.append(event["type"]))
    publisher.publish("chat.started", context(), {"state": "started"})
    unsubscribe()
    publisher.publish("chat.delta", context(), {"text": "ignored"})
    assert seen == ["chat.started"]
