from __future__ import annotations

import pytest

from python_core.rpc.context import RpcContext
from python_core.rpc.event_publisher import RpcEventPublisher
from python_core.rpc.schema.schema_hash import load_catalog
from python_core.rpc.tasks import TaskRegistry, TaskStateError


def context(request_id: str = "req_task") -> RpcContext:
    return RpcContext(
        request_id=request_id,
        trace_id="trace_task",
        parent_trace_id=None,
        session_id="sess_task",
        deadline_ms=30000,
    )


def test_long_task_accepted_response_has_no_business_result() -> None:
    registry = TaskRegistry()
    accepted = registry.accept_long_task("req_task", "chat.send")
    assert accepted["status"] == "accepted"
    assert accepted["request_id"] == "req_task"
    assert accepted["task_type"] == "chat.send"
    assert "result" not in accepted


def test_terminal_event_is_single_cas_exit() -> None:
    publisher = RpcEventPublisher()
    registry = TaskRegistry(event_publisher=publisher)
    registry.accept_long_task("req_task", "chat.send")
    event = registry.publish_terminal_event(context(), "chat.done", "done", summary={"ok": True})
    assert event["type"] == "chat.done"
    assert registry.snapshot("req_task")["task_state"] == "done"
    with pytest.raises(TaskStateError) as exc:
        registry.publish_terminal_event(context(), "chat.done", "done", summary={})
    assert exc.value.rpc_error.code == "rpc.duplicate_terminal"


def test_cancel_unknown_and_known_task_are_distinct() -> None:
    registry = TaskRegistry()
    assert registry.cancel("missing")["status"] == "not_found"
    registry.accept_long_task("req_task", "chat.send", context=context())
    result = registry.cancel("req_task", "user")
    assert result["status"] == "cancelled"
    assert result["terminal_state"] == "cancelled"
    assert registry.snapshot("req_task")["task_state"] == "cancelled"
    events = registry.event_publisher.drain()
    assert events[-1]["type"] == "chat.cancelled"
    assert events[-1]["payload"]["terminal_state"] == "cancelled"


def test_cancel_is_idempotent_after_terminal_state() -> None:
    registry = TaskRegistry()
    registry.accept_long_task("req_task", "chat.send", context=context())
    assert registry.cancel("req_task", "user")["status"] == "cancelled"
    result = registry.cancel("req_task", "again")
    assert result["status"] == "already_terminal"
    assert result["terminal_state"] == "cancelled"


def test_sidecar_restart_marks_pending_tasks_error() -> None:
    registry = TaskRegistry()
    registry.accept_long_task("req_task", "chat.send")
    assert registry.mark_pending_restarted() == 1
    snapshot = registry.snapshot("req_task")
    assert snapshot["task_state"] == "error"


def test_cancelled_events_match_catalog_for_long_tasks() -> None:
    catalog = load_catalog()
    event_specs = {event["type"]: event for event in catalog["events"]}
    long_tasks = [method for method in catalog["methods"] if method["long_task"]]
    for method in long_tasks:
        expected_cancel_events = [
            event
            for event in method["events"]
            if event_specs[event]["payload"].get("terminal_state", {}).get("value") == "cancelled"
        ]
        if not expected_cancel_events:
            continue
        request_id = f"req_{method['method'].replace('.', '_')}"
        registry = TaskRegistry()
        registry.accept_long_task(request_id, method["method"], context=context(request_id))

        result = registry.cancel(request_id, "contract")

        assert result["status"] == "cancelled"
        events = registry.event_publisher.drain()
        assert events[-1]["type"] in expected_cancel_events
        assert events[-1]["payload"]["terminal_state"] == "cancelled"
