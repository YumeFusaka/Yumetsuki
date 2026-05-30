from __future__ import annotations

from python_core.rpc.schema.schema_hash import load_catalog
from python_core.rpc.schema.validate import event_names, method_names, validate_catalog


EXPECTED_METHODS = {
    "sidecar.hello", "sidecar.health", "sidecar.shutdown", "sidecar.cancel", "sidecar.task_snapshot",
    "config.get_all", "config.save_api", "config.save_system", "config.save_memory", "config.save_agent", "config.save_mcp", "config.validate",
    "character.list", "character.get", "character.save", "character.sync_assets", "character.delete", "character.protect_core_files",
    "chat.send", "chat.retry", "chat.proactive_state",
    "proactive.start", "proactive.stop", "proactive.notify_interaction", "proactive.update_context",
    "tts.synthesize", "stt.begin_recording", "stt.stop_recording", "stt.transcribe",
    "ocr.capture", "ocr.recognize", "ocr.cleanup",
    "logs.query", "logs.subscribe", "logs.export", "logs.open_location",
    "tools.list", "tools.call", "tools.audit_query",
    "plugins.refresh", "plugins.enable", "plugins.disable", "plugins.import", "plugins.status",
    "mcp.list_servers", "mcp.save_server", "mcp.refresh", "mcp.call_tool", "mcp.stop_server",
    "security.approve", "security.deny", "security.revoke_grant", "security.list_grants",
    "diagnostics.run", "diagnostics.export", "diagnostics.open_report",
    "handles.read_range", "handles.read_page", "handles.release", "handles.stat",
}


REQUIRED_EVENTS = {
    "security.confirm_required",
    "chat.started", "chat.delta", "chat.done", "chat.error", "chat.cancelled",
    "log.appended",
    "diagnostics.progress", "diagnostics.done", "diagnostics.error",
    "tool.audit",
    "sidecar.crashed", "sidecar.restarted",
}


def test_catalog_contains_exact_phase1a_method_set() -> None:
    catalog = load_catalog()
    assert set(method_names(catalog)) == EXPECTED_METHODS


def test_required_method_fields_are_executable_schema() -> None:
    catalog = load_catalog()
    assert validate_catalog(catalog) == []


def test_security_confirm_required_is_event_only() -> None:
    catalog = load_catalog()
    assert "security.confirm_required" not in set(method_names(catalog))
    assert "security.confirm_required" in set(event_names(catalog))
    event = next(item for item in catalog["events"] if item["event"] == "security.confirm_required")
    assert event["event_only"] is True
    assert set(event["payload"]) >= {
        "request_id",
        "confirm_token",
        "capability",
        "scope_hash",
        "expires_at_ms",
        "user_message",
        "audit_summary",
    }


def test_sidecar_cancel_is_only_cancel_wire_method() -> None:
    methods = set(method_names(load_catalog()))
    cancel_like = {name for name in methods if "cancel" in name}
    assert cancel_like == {"sidecar.cancel"}


def test_business_stop_methods_do_not_cancel_arbitrary_requests() -> None:
    catalog = load_catalog()
    stop_methods = {method["method"]: method for method in catalog["methods"] if method["method"].endswith(".stop") or method["method"].endswith(".stop_recording") or method["method"].endswith(".stop_server")}
    assert set(stop_methods) == {"proactive.stop", "stt.stop_recording", "mcp.stop_server"}
    for method in stop_methods.values():
        assert method["long_task"] is False
        assert method["cancels_request"] is False
        assert "request_id" not in method["params"]
        assert not any(event.endswith(".cancelled") for event in method["events"])


def test_required_events_are_declared() -> None:
    assert REQUIRED_EVENTS <= set(event_names(load_catalog()))
