from __future__ import annotations

from python_core.rpc.tasks import TaskRegistry


def test_pending_requests_are_marked_restarted_once_per_generation() -> None:
    registry = TaskRegistry(sidecar_generation=3)
    registry.accept_long_task("req_chat", "chat.send")
    registry.accept_long_task("req_tts", "tts.synthesize")

    events = registry.mark_pending_restarted()
    duplicate = registry.mark_pending_restarted()

    assert len(events) == 2
    assert duplicate == []
    assert {event["payload"]["error"]["code"] for event in events} == {"sidecar.restarted"}
    assert {item["state"] for item in registry.snapshot()} == {"error"}
