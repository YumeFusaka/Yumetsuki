from __future__ import annotations

from python_core.rpc.schema.schema_hash import compute_schema_hash, load_catalog
from python_core.rpc.schema.validate import event_types, method_names, validate_catalog


EXPECTED_METHODS = {
    "sidecar.hello",
    "sidecar.health",
    "sidecar.shutdown",
    "sidecar.cancel",
    "sidecar.task_snapshot",
    "config.get_all",
    "config.save_api",
    "config.save_system",
    "config.save_memory",
    "config.save_agent",
    "config.save_mcp",
    "config.validate",
    "character.list",
    "character.get",
    "character.save",
    "character.sync_assets",
    "character.delete",
    "character.protect_core_files",
    "chat.send",
    "chat.retry",
    "chat.proactive_state",
    "proactive.start",
    "proactive.stop",
    "proactive.notify_interaction",
    "proactive.update_context",
    "tts.synthesize",
    "stt.begin_recording",
    "stt.stop_recording",
    "stt.transcribe",
    "ocr.capture",
    "ocr.recognize",
    "ocr.cleanup",
    "logs.query",
    "logs.subscribe",
    "logs.export",
    "logs.open_location",
    "tools.list",
    "tools.call",
    "tools.audit_query",
    "plugins.refresh",
    "plugins.enable",
    "plugins.disable",
    "plugins.import",
    "plugins.status",
    "mcp.list_servers",
    "mcp.save_server",
    "mcp.refresh",
    "mcp.call_tool",
    "mcp.stop_server",
    "security.approve",
    "security.deny",
    "security.revoke_grant",
    "security.list_grants",
    "diagnostics.run",
    "diagnostics.export",
    "diagnostics.open_report",
    "handles.read_range",
    "handles.read_page",
    "handles.release",
    "handles.stat",
}


def test_catalog_is_valid_and_complete_for_phase5() -> None:
    catalog = load_catalog()
    validate_catalog(catalog)
    assert method_names(catalog) == EXPECTED_METHODS
    assert "security.confirm_required" not in method_names(catalog)
    assert "security.confirm_required" in event_types(catalog)


def test_sidecar_cancel_is_only_wire_cancel_method() -> None:
    names = method_names()
    cancel_methods = [name for name in names if name != "sidecar.cancel" and name.endswith(".cancel")]
    assert cancel_methods == []


def test_schema_hash_is_stable_sha256() -> None:
    digest = compute_schema_hash()
    assert len(digest) == 64
    assert digest == compute_schema_hash(load_catalog())
