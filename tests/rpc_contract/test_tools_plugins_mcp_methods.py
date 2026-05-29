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
            "trace_id": "trace_tools_plugins_mcp",
            "parent_trace_id": None,
            "session_id": "sess_tools_plugins_mcp",
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


def test_tools_list_call_and_audit_are_safe_facades() -> None:
    harness = RpcHarness()

    list_response, _list_events = harness.dispatch("tools.list", {"include_disabled": True})
    call_response, call_events = harness.dispatch(
        "tools.call",
        {"tool_name": "dryrun.echo", "source": "contract", "arguments": {"value": "hello"}, "dry_run": True},
    )
    audit_response, _audit_events = harness.dispatch("tools.audit_query", {"limit": 1})
    confirm_error, _confirm_events = harness.dispatch(
        "tools.call",
        {"tool_name": "dryrun.echo", "source": "contract", "arguments": {"value": "hello"}},
        request_id="req_tools_call_confirm",
    )

    assert list_response["result"]["items"][0]["tool_name"] == "example_echo__echo"
    assert call_response["result"]["status"] == "accepted"
    assert [event["type"] for event in call_events] == ["tool.started", "tool.audit", "tool.result"]
    assert len(_terminal_events(call_events)) == 1
    assert audit_response["result"]["items"][0]["audit_entry_id"] == "dryrun-audit-1"
    assert confirm_error["error"]["code"] == "tool.confirm_required"


def test_plugins_methods_return_status_and_long_task_events() -> None:
    harness = RpcHarness()

    refresh_response, refresh_events = harness.dispatch("plugins.refresh", {})
    enable_response, enable_events = harness.dispatch(
        "plugins.enable",
        {"plugin_id": "example-plugin", "confirm_token": "confirm"},
    )
    disable_response, disable_events = harness.dispatch("plugins.disable", {"plugin_id": "example-plugin"})
    import_response, import_events = harness.dispatch(
        "plugins.import",
        {"package_handle": "handle:file:plugin", "confirm_token": "confirm"},
    )
    status_response, _status_events = harness.dispatch("plugins.status", {"plugin_id": "example-plugin"})

    assert refresh_response["result"]["task_type"] == "plugins.refresh"
    assert [event["type"] for event in refresh_events] == ["plugin.status", "plugin.done"]
    assert len(_terminal_events(refresh_events)) == 1
    assert enable_response["result"]["enabled"] is True
    assert enable_events[-1]["type"] == "plugin.status"
    assert disable_response["result"]["disabled"] is True
    assert disable_events[-1]["type"] == "plugin.status"
    assert import_response["result"]["status"] == "accepted"
    assert import_events[-1]["type"] == "plugin.done"
    assert status_response["result"]["status"]["plugin_id"] == "example-plugin"


def test_mcp_methods_and_security_grants_use_headless_facades() -> None:
    harness = RpcHarness()

    list_response, _list_events = harness.dispatch("mcp.list_servers", {"include_disabled": True})
    save_response, save_events = harness.dispatch(
        "mcp.save_server",
        {"draft": {"server_id": "local-dev"}, "base_version": 1, "confirm_token": "confirm"},
    )
    refresh_response, refresh_events = harness.dispatch("mcp.refresh", {"server_id": "local-dev"})
    call_response, call_events = harness.dispatch(
        "mcp.call_tool",
        {"server_id": "local-dev", "tool_name": "echo", "arguments": {"value": "hello"}},
    )
    stop_response, stop_events = harness.dispatch("mcp.stop_server", {"server_id": "local-dev"})
    grants_response, _grants_events = harness.dispatch("security.list_grants", {})

    assert list_response["result"]["servers"] == []
    assert save_response["result"]["applied_version"] == 2
    assert save_events[-1]["type"] == "mcp.config_changed"
    assert refresh_response["result"]["task_type"] == "mcp.refresh"
    assert refresh_events[-1]["type"] == "mcp.done"
    assert len(_terminal_events(refresh_events)) == 1
    assert call_response["result"]["status"] == "accepted"
    assert call_events[-1]["type"] == "mcp.tool_done"
    assert len(_terminal_events(call_events)) == 1
    assert stop_response["result"]["stopped"] is True
    assert stop_events[-1]["type"] == "mcp.status"
    assert grants_response["result"]["grants"][0]["grant_id"] == "diagnostics-readonly"


def test_security_approval_methods_publish_security_events() -> None:
    harness = RpcHarness()

    approve_response, approve_events = harness.dispatch(
        "security.approve",
        {"confirmation_id": "confirmation-1", "confirm_token": "confirm"},
    )
    deny_response, deny_events = harness.dispatch("security.deny", {"confirmation_id": "confirmation-1"})
    revoke_response, revoke_events = harness.dispatch("security.revoke_grant", {"grant_id": "grant-1"})

    assert approve_response["result"]["approved"] is True
    assert approve_events[-1]["type"] == "security.approved"
    assert deny_response["result"]["denied"] is True
    assert deny_events[-1]["type"] == "security.denied"
    assert revoke_response["result"]["revoked"] is True
    assert revoke_events[-1]["type"] == "security.grant_revoked"
