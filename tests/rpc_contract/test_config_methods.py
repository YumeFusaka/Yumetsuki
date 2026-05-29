from __future__ import annotations

import sys
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
            "trace_id": f"trace_{method.replace('.', '_')}",
            "parent_trace_id": None,
            "session_id": "sess_rpc_contract",
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


def test_sidecar_hello_reports_catalog_capabilities_without_qt_import() -> None:
    qt_modules_before = {name for name in sys.modules if name == "PySide6" or name.startswith("PySide6.")}
    harness = RpcHarness()

    response, _events = harness.dispatch("sidecar.hello", {"supported_protocol_versions": [1]})

    assert response["ok"] is True
    assert set(response["result"]["capabilities"]) == harness.registry.catalog_methods
    qt_modules_after = {name for name in sys.modules if name == "PySide6" or name.startswith("PySide6.")}
    assert qt_modules_after == qt_modules_before


def test_config_get_all_returns_redacted_snapshot() -> None:
    response, events = RpcHarness().dispatch("config.get_all", {"scope": "api"})

    assert response["ok"] is True
    assert response["result"]["version"] == 1
    snapshot = response["result"]["redacted_snapshot"]
    assert snapshot["scope"] == "api"
    assert snapshot["api"]["api_key"]["is_set"] is False
    assert events == []


def test_config_save_methods_publish_safe_change_events() -> None:
    harness = RpcHarness()
    cases = [
        ("config.save_api", {"draft": {"provider": "openai_compat"}, "base_version": 1, "confirm_token": "confirm"}, "config.changed"),
        ("config.save_system", {"draft": {"theme": "sakura"}, "base_version": 1, "confirm_token": "confirm"}, "config.changed"),
        ("config.save_memory", {"draft": {"enabled": False}, "base_version": 1, "confirm_token": "confirm"}, "config.changed"),
        ("config.save_agent", {"draft": {"planner_enabled": False}, "base_version": 1, "confirm_token": "confirm"}, "config.changed"),
        ("config.save_mcp", {"draft": {"servers": []}, "base_version": 1, "confirm_token": "confirm"}, "mcp.config_changed"),
    ]

    for method, params, first_event in cases:
        response, events = harness.dispatch(method, params)

        assert response["ok"] is True
        assert response["result"]["applied_version"] == 2
        assert events[0]["type"] == first_event


def test_config_validate_and_required_param_errors_use_existing_codes() -> None:
    harness = RpcHarness()

    ok_response, _events = harness.dispatch("config.validate", {"scope": "api", "draft": {}})
    error_response, _error_events = harness.dispatch("config.validate", {"scope": "api"})

    assert ok_response["ok"] is True
    assert ok_response["result"]["validation_result"]["ok"] is True
    assert error_response["ok"] is False
    assert error_response["error"]["code"] == "rpc.invalid_params"
