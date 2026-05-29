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
            "trace_id": "trace_logs_diagnostics",
            "parent_trace_id": None,
            "session_id": "sess_logs_diagnostics",
            "deadline_ms": 30000,
        }
        response = self.registry.dispatch(validate_request_envelope(payload), self.runtime)
        validate_response_envelope(response)
        events = self.runtime.task_registry.event_publisher.drain()
        for event in events:
            validate_event_envelope(event)
        if not response["ok"]:
            assert response["error"]["code"] != "sidecar.not_ready"
        return response, events


def _terminal_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [event for event in events if event["payload"].get("terminal_state") in {"done", "error", "cancelled"}]


def test_logs_query_open_and_handle_methods_return_contract_shapes() -> None:
    harness = RpcHarness()

    query_response, query_events = harness.dispatch("logs.query", {"channel": "system", "limit": 1})
    open_response, _open_events = harness.dispatch("logs.open_location", {"report_id": "report-1"})
    range_response, _range_events = harness.dispatch(
        "handles.read_range",
        {"handle_id": "handle:text:report", "start": 0, "length": 4},
    )
    page_response, _page_events = harness.dispatch("handles.read_page", {"handle_id": "handle:text:report"})
    stat_response, _stat_events = harness.dispatch("handles.stat", {"handle_id": "handle:text:report"})
    release_response, _release_events = harness.dispatch("handles.release", {"handle_id": "handle:text:report"})

    assert query_response["result"]["items"] == []
    assert query_events == []
    assert open_response["result"]["opened"] is False
    assert range_response["result"]["chunk"]
    assert page_response["result"]["page"]["handle_id"] == "handle:text:report"
    assert stat_response["result"]["kind"] == "resource"
    assert release_response["result"]["released"] is True


def test_logs_long_methods_are_accepted_and_emit_terminal_once() -> None:
    harness = RpcHarness()

    subscribe_response, subscribe_events = harness.dispatch("logs.subscribe", {"channel": "system"})
    export_response, export_events = harness.dispatch("logs.export", {"channel": "system", "format": "json"})

    assert subscribe_response["result"]["task_type"] == "logs.subscribe"
    assert [event["type"] for event in subscribe_events] == ["log.batch", "log.done"]
    assert len(_terminal_events(subscribe_events)) == 1
    assert export_response["result"]["task_type"] == "logs.export"
    assert [event["type"] for event in export_events] == ["log.export_progress", "log.export_done"]
    assert len(_terminal_events(export_events)) == 1


def test_diagnostics_run_export_and_open_report_are_safe_facades() -> None:
    harness = RpcHarness()

    run_response, run_events = harness.dispatch("diagnostics.run", {"checks": ["runtime"], "include_sensitive": False})
    report_handle = run_events[-1]["payload"]["summary"]["report_handle"]
    export_response, export_events = harness.dispatch("diagnostics.export", {"report_handle": report_handle, "format": "json"})
    open_response, open_events = harness.dispatch("diagnostics.open_report", {"report_id": "report-1"})

    assert run_response["result"]["status"] == "accepted"
    assert [event["type"] for event in run_events] == ["diagnostic.progress", "diagnostic.done"]
    assert len(_terminal_events(run_events)) == 1
    assert report_handle.startswith("handle:report:")
    assert export_response["result"]["task_type"] == "diagnostics.export"
    assert export_events[-1]["type"] == "diagnostic.done"
    assert export_events[-1]["payload"]["summary"]["export_handle"].startswith("handle:report:")
    assert len(_terminal_events(export_events)) == 1
    assert open_response["result"]["opened"] is False
    assert open_events == []


def test_logs_and_diagnostics_validation_errors_use_existing_codes() -> None:
    harness = RpcHarness()

    logs_error, _logs_events = harness.dispatch("logs.query", {"limit": -1})
    diagnostics_error, _diagnostics_events = harness.dispatch("diagnostics.run", {"checks": [], "include_sensitive": True})

    assert logs_error["error"]["code"] == "rpc.invalid_params"
    assert diagnostics_error["error"]["code"] == "security.permission_denied"
