from __future__ import annotations

import time

import pytest

from python_core.rpc.tasks import TaskRegistry, TaskState


def test_short_task_lifecycle_and_late_response_drop() -> None:
    registry = TaskRegistry()
    handle = registry.create_short_task("req_short", "config.get_all", deadline=time.time() + 10)
    assert handle.state == TaskState.CREATED
    registry.mark_running("req_short")
    assert registry.complete_short_task("req_short", ok=True) is True
    assert registry.complete_short_task("req_short", ok=True) is False

    registry.create_short_task("req_late", "config.get_all", deadline=time.time() - 1)
    assert registry.complete_short_task("req_late", ok=True) is False


def test_long_task_acceptance_and_terminal_event() -> None:
    registry = TaskRegistry(sidecar_generation=7)
    accepted = registry.accept_long_task("req_chat", "chat")
    assert accepted == {
        "status": "accepted",
        "request_id": "req_chat",
        "task_type": "chat",
        "sidecar_generation": 7,
    }
    registry.mark_streaming("req_chat")
    done = registry.publish_terminal_event("req_chat", "done", "ok")
    assert done["payload"]["state"] == "done"
    assert done["sequence"] == 1
    with pytest.raises(ValueError, match="duplicate_terminal"):
        registry.publish_terminal_event("req_chat", "done", "again")


def test_accepted_task_can_finish_without_streaming() -> None:
    registry = TaskRegistry()
    registry.accept_long_task("req_direct", "chat")
    done = registry.publish_terminal_event("req_direct", "done", "ok")
    assert done["payload"]["state"] == "done"


def test_cancel_is_idempotent_after_terminal() -> None:
    registry = TaskRegistry()
    registry.accept_long_task("req_cancel", "chat")
    assert registry.cancel("req_cancel")["state"] == "cancelling"
    terminal = registry.publish_terminal_event("req_cancel", "cancelled", "user cancelled")
    assert terminal["payload"]["state"] == "cancelled"
    assert registry.cancel("req_cancel")["state"] == "cancelled"


def test_cancel_and_timeout_race_only_one_terminal() -> None:
    registry = TaskRegistry()
    registry.accept_long_task("req_race", "chat")
    registry.cancel("req_race")
    registry.publish_terminal_event("req_race", "cancelled", "cancel wins")
    with pytest.raises(ValueError, match="duplicate_terminal"):
        registry.publish_terminal_event("req_race", "error", "timeout")


def test_sidecar_restart_marks_pending_requests() -> None:
    registry = TaskRegistry()
    registry.accept_long_task("req_pending", "chat")
    events = registry.mark_pending_restarted()
    assert events[0]["payload"]["state"] == "error"
    assert events[0]["payload"]["error"]["code"] == "sidecar.restarted"
