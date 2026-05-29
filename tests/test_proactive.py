from __future__ import annotations

from typing import Any

from python_core.rpc.envelope import validate_event_envelope, validate_request_envelope, validate_response_envelope
from python_core.rpc.registry import MethodRegistry, SidecarRuntime
from python_core.runtime_paths import RuntimePaths


class RpcHarness:
    def __init__(self) -> None:
        self.registry = MethodRegistry()
        self.runtime = SidecarRuntime.create(RuntimePaths.temporary())

    def dispatch(
        self,
        method: str,
        params: dict[str, Any] | None = None,
        request_id: str | None = None,
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        payload = {
            "kind": "request",
            "request_id": request_id or f"req_{method.replace('.', '_')}",
            "method": method,
            "params": params or {},
            "protocol_version": 1,
            "trace_id": "trace_proactive",
            "parent_trace_id": None,
            "session_id": "sess_proactive",
            "deadline_ms": 30000,
        }
        response = self.registry.dispatch(validate_request_envelope(payload), self.runtime)
        validate_response_envelope(response)
        events = self.runtime.task_registry.event_publisher.drain()
        for event in events:
            validate_event_envelope(event)
        return response, events


def test_chat_and_proactive_short_methods_publish_status_events() -> None:
    harness = RpcHarness()

    proactive_state, proactive_state_events = harness.dispatch(
        "chat.proactive_state",
        {"passive_state": True, "window_visible": False, "last_interaction_ms": 1},
    )
    start_response, start_events = harness.dispatch("proactive.start", {})
    notify_response, notify_events = harness.dispatch(
        "proactive.notify_interaction",
        {"interaction_type": "chat", "timestamp_ms": 1},
    )
    update_response, update_events = harness.dispatch("proactive.update_context", {"character_summary": {"name": "test"}})
    stop_response, stop_events = harness.dispatch("proactive.stop", {"reason": "test"})

    assert proactive_state["result"]["accepted_state"] is True
    assert proactive_state_events[-1]["type"] == "chat.proactive_state_changed"
    assert start_response["result"]["started"] is True
    assert start_events[-1]["type"] == "proactive.status"
    assert notify_response["result"]["accepted"] is True
    assert notify_events == []
    assert update_response["result"]["accepted"] is True
    assert update_events[-1]["type"] == "proactive.context_updated"
    assert stop_response["result"]["stopped"] is True
    assert stop_events[-1]["type"] == "proactive.status"


def test_proactive_notify_interaction_rejects_missing_required_fields() -> None:
    response, _events = RpcHarness().dispatch("proactive.notify_interaction", {"interaction_type": "chat"})

    assert response["ok"] is False
    assert response["error"]["code"] == "rpc.invalid_params"


def test_sidecar_cancel_still_routes_through_headless_rpc() -> None:
    harness = RpcHarness()
    harness.runtime.task_registry.accept_long_task(
        request_id="req_pending_chat",
        task_type="chat.send",
        context=None,
    )

    response, events = harness.dispatch(
        "sidecar.cancel",
        {"request_id": "req_pending_chat", "reason": "user"},
        request_id="req_cancel_chat",
    )

    assert response["ok"] is True
    assert response["result"]["status"] == "cancelled"
    assert events[-1]["type"] == "chat.cancelled"
