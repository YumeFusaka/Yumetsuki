from __future__ import annotations

import time
import json
from pathlib import Path
from typing import Any, Callable, TYPE_CHECKING

from .context import RpcContext
from .errors import RpcError, make_error

if TYPE_CHECKING:
    from .envelope import RequestEnvelope
    from .registry import SidecarRuntime


Handler = Callable[["RequestEnvelope", "SidecarRuntime"], dict[str, Any]]

DRY_RUN_TOOL_NAME = "dryrun.echo"
DRY_RUN_DISABLED_TOOL_NAME = "dryrun.shell"
DEFAULT_PLUGIN_ID = "example-plugin"
DEFAULT_MCP_SERVER_ID = "local-dev"
DEFAULT_GRANT_ID = "diagnostics-readonly"


class ServiceError(Exception):
    def __init__(self, rpc_error: RpcError):
        super().__init__(rpc_error.message)
        self.rpc_error = rpc_error


def build_service_handlers() -> dict[str, Handler]:
    return {
        "config.get_all": _handle_config_get_all,
        "config.save_api": _handle_config_save_api,
        "config.save_system": _handle_config_save_system,
        "config.save_memory": _handle_config_save_memory,
        "config.save_agent": _handle_config_save_agent,
        "config.save_mcp": _handle_config_save_mcp,
        "config.validate": _handle_config_validate,
        "character.list": _handle_character_list,
        "character.get": _handle_character_get,
        "character.save": _handle_character_save,
        "character.sync_assets": _handle_character_sync_assets,
        "character.delete": _handle_character_delete,
        "character.protect_core_files": _handle_character_protect_core_files,
        "chat.send": _handle_chat_send,
        "chat.retry": _handle_chat_retry,
        "chat.proactive_state": _handle_chat_proactive_state,
        "proactive.start": _handle_proactive_start,
        "proactive.stop": _handle_proactive_stop,
        "proactive.notify_interaction": _handle_proactive_notify_interaction,
        "proactive.update_context": _handle_proactive_update_context,
        "tts.synthesize": _handle_tts_synthesize,
        "stt.begin_recording": _handle_stt_begin_recording,
        "stt.stop_recording": _handle_stt_stop_recording,
        "stt.transcribe": _handle_stt_transcribe,
        "ocr.capture": _handle_ocr_capture,
        "ocr.recognize": _handle_ocr_recognize,
        "ocr.cleanup": _handle_ocr_cleanup,
        "logs.query": _handle_logs_query,
        "logs.subscribe": _handle_logs_subscribe,
        "logs.export": _handle_logs_export,
        "logs.open_location": _handle_logs_open_location,
        "tools.list": _handle_tools_list,
        "tools.call": _handle_tools_call,
        "tools.audit_query": _handle_tools_audit_query,
        "plugins.refresh": _handle_plugins_refresh,
        "plugins.enable": _handle_plugins_enable,
        "plugins.disable": _handle_plugins_disable,
        "plugins.import": _handle_plugins_import,
        "plugins.status": _handle_plugins_status,
        "mcp.list_servers": _handle_mcp_list_servers,
        "mcp.save_server": _handle_mcp_save_server,
        "mcp.refresh": _handle_mcp_refresh,
        "mcp.call_tool": _handle_mcp_call_tool,
        "mcp.stop_server": _handle_mcp_stop_server,
        "security.approve": _handle_security_approve,
        "security.deny": _handle_security_deny,
        "security.revoke_grant": _handle_security_revoke_grant,
        "security.list_grants": _handle_security_list_grants,
        "diagnostics.run": _handle_diagnostics_run,
        "diagnostics.export": _handle_diagnostics_export,
        "diagnostics.open_report": _handle_diagnostics_open_report,
        "handles.read_range": _handle_handles_read_range,
        "handles.read_page": _handle_handles_read_page,
        "handles.release": _handle_handles_release,
        "handles.stat": _handle_handles_stat,
    }


def _handle_config_get_all(request: "RequestEnvelope", runtime: "SidecarRuntime") -> dict[str, Any]:
    scope = _optional_str(request.params, "scope", default="all")
    return {"version": 1, "redacted_snapshot": _config_snapshot(runtime, scope)}


def _handle_config_save_api(request: "RequestEnvelope", runtime: "SidecarRuntime") -> dict[str, Any]:
    _require_object(request.params, "draft")
    version = _next_version(request.params)
    _require_token(request.params, "confirm_token")
    _apply_config_draft(runtime, "api", request.params["draft"])
    _publish(request, runtime, "config.changed", {"changed_scopes": ["api"]})
    return {"applied_version": version, "redacted_snapshot": _config_snapshot(runtime, "api")}


def _handle_config_save_system(request: "RequestEnvelope", runtime: "SidecarRuntime") -> dict[str, Any]:
    _require_object(request.params, "draft")
    version = _next_version(request.params)
    _require_token(request.params, "confirm_token")
    _apply_config_draft(runtime, "system", request.params["draft"])
    changed = ["system"]
    _publish(request, runtime, "config.changed", {"changed_scopes": changed})
    _publish(request, runtime, "chat.config_applied", {"summary": {"changed_scopes": changed, "applied": True}})
    return {"applied_version": version, "changed_scopes": changed}


def _handle_config_save_memory(request: "RequestEnvelope", runtime: "SidecarRuntime") -> dict[str, Any]:
    _require_object(request.params, "draft")
    version = _next_version(request.params)
    _require_token(request.params, "confirm_token")
    _apply_config_draft(runtime, "memory", request.params["draft"])
    _publish(request, runtime, "config.changed", {"changed_scopes": ["memory"]})
    return {"applied_version": version, "redacted_snapshot": _config_snapshot(runtime, "memory")}


def _handle_config_save_agent(request: "RequestEnvelope", runtime: "SidecarRuntime") -> dict[str, Any]:
    _require_object(request.params, "draft")
    version = _next_version(request.params)
    _require_token(request.params, "confirm_token")
    _apply_config_draft(runtime, "agent", request.params["draft"])
    _publish(request, runtime, "config.changed", {"changed_scopes": ["agent"]})
    return {"applied_version": version, "redacted_snapshot": _config_snapshot(runtime, "agent")}


def _handle_config_save_mcp(request: "RequestEnvelope", runtime: "SidecarRuntime") -> dict[str, Any]:
    _require_object(request.params, "draft")
    version = _next_version(request.params)
    _require_token(request.params, "confirm_token")
    _apply_config_draft(runtime, "mcp", request.params["draft"])
    summary = {"servers": [], "applied": True}
    _publish(request, runtime, "mcp.config_changed", {"summary": summary})
    return {"applied_version": version, "server_summary": summary}


def _handle_config_validate(request: "RequestEnvelope", runtime: "SidecarRuntime") -> dict[str, Any]:
    scope = _require_str(request.params, "scope")
    _require_object(request.params, "draft")
    validation = _validate_config_draft(runtime, scope, request.params["draft"])
    return {"validation_result": {"ok": validation["ok"], "scope": scope, "issues": validation["issues"]}}


def _handle_character_list(request: "RequestEnvelope", runtime: "SidecarRuntime") -> dict[str, Any]:
    include_disabled = _optional_bool(request.params, "include_disabled", default=False)
    items = _character_items(runtime, include_disabled=include_disabled)
    if not items:
        items = [_character_summary("default", enabled=True)]
    return {"items": items}


def _handle_character_get(request: "RequestEnvelope", runtime: "SidecarRuntime") -> dict[str, Any]:
    character_id = _require_str(request.params, "character_id")
    return {"redacted_character": _character_detail(character_id, runtime)}


def _handle_character_save(request: "RequestEnvelope", runtime: "SidecarRuntime") -> dict[str, Any]:
    draft = _require_object(request.params, "draft")
    version = _next_version(request.params)
    _require_token(request.params, "confirm_token")
    character_id = str(draft.get("character_id") or "default")
    summary = {"character_id": character_id, "assets_checked": _character_asset_count(character_id, runtime), "saved": True}
    _publish(request, runtime, "character.changed", {"summary": summary})
    return {"applied_version": version, "asset_summary": summary}


def _handle_character_sync_assets(request: "RequestEnvelope", runtime: "SidecarRuntime") -> dict[str, Any]:
    character_id = _require_str(request.params, "character_id")
    asset_handles = _require_array(request.params, "asset_handles")
    return _finish_long_task(
        request,
        runtime,
        task_type="character.sync_assets",
        owner="character",
        progress_events=[("character.assets_progress", {"progress": 1.0})],
        terminal_event_type="character.assets_done",
        summary={"character_id": character_id, "asset_count": len(asset_handles), "synced": True},
    )


def _handle_character_delete(request: "RequestEnvelope", runtime: "SidecarRuntime") -> dict[str, Any]:
    character_id = _require_str(request.params, "character_id")
    _require_token(request.params, "confirm_token")
    protected = character_id == "default"
    _publish(request, runtime, "character.changed", {"summary": {"character_id": character_id, "deleted": not protected}})
    return {"deleted": not protected, "protected": protected}


def _handle_character_protect_core_files(request: "RequestEnvelope", runtime: "SidecarRuntime") -> dict[str, Any]:
    character_id = _require_str(request.params, "character_id")
    return {"protection_summary": {"character_id": character_id, "protected": True, "scoped": True}}


def _handle_chat_send(request: "RequestEnvelope", runtime: "SidecarRuntime") -> dict[str, Any]:
    text = _require_str(request.params, "text")
    session_id = _require_str(request.params, "session_id")
    return _finish_chat(request, runtime, "chat.send", text=text, session_id=session_id, dry_run=False)


def _handle_chat_retry(request: "RequestEnvelope", runtime: "SidecarRuntime") -> dict[str, Any]:
    source_request_id = _require_str(request.params, "source_request_id")
    return _finish_chat(
        request,
        runtime,
        "chat.retry",
        text=f"retry for {source_request_id}",
        session_id=request.session_id,
        dry_run=False,
    )


def _handle_chat_proactive_state(request: "RequestEnvelope", runtime: "SidecarRuntime") -> dict[str, Any]:
    passive_state = _require_bool(request.params, "passive_state")
    window_visible = _require_bool(request.params, "window_visible")
    last_interaction_ms = _require_int(request.params, "last_interaction_ms", min_value=0)
    accepted = passive_state or window_visible or last_interaction_ms >= 0
    _publish(
        request,
        runtime,
        "chat.proactive_state_changed",
        {"summary": {"accepted_state": accepted, "window_visible": window_visible}},
    )
    return {"accepted_state": accepted}


def _handle_proactive_start(request: "RequestEnvelope", runtime: "SidecarRuntime") -> dict[str, Any]:
    _optional_str(request.params, "policy_version", default="")
    _publish(request, runtime, "proactive.status", {"status": "started"})
    return {"started": True}


def _handle_proactive_stop(request: "RequestEnvelope", runtime: "SidecarRuntime") -> dict[str, Any]:
    _optional_str(request.params, "reason", default="")
    _publish(request, runtime, "proactive.status", {"status": "stopped"})
    return {"stopped": True}


def _handle_proactive_notify_interaction(request: "RequestEnvelope", runtime: "SidecarRuntime") -> dict[str, Any]:
    _require_str(request.params, "interaction_type")
    _require_int(request.params, "timestamp_ms", min_value=0)
    return {"accepted": True}


def _handle_proactive_update_context(request: "RequestEnvelope", runtime: "SidecarRuntime") -> dict[str, Any]:
    _optional_object(request.params, "character_summary")
    _optional_str(request.params, "visual_summary_handle", default=None)
    _publish(request, runtime, "proactive.context_updated", {"summary": {"accepted": True, "context_applied": True}})
    return {"accepted": True}


def _handle_tts_synthesize(request: "RequestEnvelope", runtime: "SidecarRuntime") -> dict[str, Any]:
    text = _require_str(request.params, "text")
    voice_config_ref = _require_str(request.params, "voice_config_ref")
    session_id = _require_str(request.params, "session_id")
    segment_handle = _resource_handle("audio", request.request_id)
    return _finish_long_task(
        request,
        runtime,
        task_type="tts.synthesize",
        owner="speech",
        progress_events=[
            ("tts.started", {"state": "started"}),
            ("tts.segment", {"segment_handle": segment_handle}),
        ],
        terminal_event_type="tts.done",
        summary={
            "text_length": len(text),
            "voice_config_ref": voice_config_ref,
            "session_id": session_id,
            "segment_count": 1,
            "generated": True,
        },
    )


def _handle_stt_begin_recording(request: "RequestEnvelope", runtime: "SidecarRuntime") -> dict[str, Any]:
    _optional_str(request.params, "device_hint", default=None)
    timeout_ms = _optional_int(request.params, "timeout_ms", default=30000, min_value=1)
    return _finish_long_task(
        request,
        runtime,
        task_type="stt.begin_recording",
        owner="speech",
        progress_events=[
            ("stt.recording", {"state": "recording"}),
            ("stt.progress", {"progress": 1.0}),
        ],
        terminal_event_type="stt.recording",
        summary={"timeout_ms": timeout_ms, "audio_handle": _resource_handle("audio", request.request_id), "recording": True},
        terminal_extra={"state": "stopped"},
    )


def _handle_stt_stop_recording(request: "RequestEnvelope", runtime: "SidecarRuntime") -> dict[str, Any]:
    recording_request_id = _require_str(request.params, "recording_request_id")
    audio_handle = _resource_handle("audio", recording_request_id)
    _publish(request, runtime, "stt.recording_stopped", {"summary": {"recording_request_id": recording_request_id}})
    return {"audio_handle": audio_handle, "no_audio": False}


def _handle_stt_transcribe(request: "RequestEnvelope", runtime: "SidecarRuntime") -> dict[str, Any]:
    audio_handle = _require_str(request.params, "audio_handle")
    language = _optional_str(request.params, "language", default=None) or "auto"
    _optional_int(request.params, "timeout_ms", default=30000, min_value=1)
    return _finish_long_task(
        request,
        runtime,
        task_type="stt.transcribe",
        owner="speech",
        progress_events=[("stt.started", {"state": "started"}), ("stt.progress", {"progress": 1.0})],
        terminal_event_type="stt.done",
        summary={"audio_handle": audio_handle, "language": language, "text": "识别结果示例", "generated": True},
    )


def _handle_ocr_capture(request: "RequestEnvelope", runtime: "SidecarRuntime") -> dict[str, Any]:
    reason = _require_str(request.params, "reason")
    _optional_object(request.params, "region")
    image_handle = _resource_handle("image", request.request_id)
    return _finish_long_task(
        request,
        runtime,
        task_type="ocr.capture",
        owner="vision",
        progress_events=[],
        terminal_event_type="ocr.capture_done",
        summary={"reason_length": len(reason), "image_handle": image_handle, "captured": True},
        terminal_extra={"image_handle": image_handle},
    )


def _handle_ocr_recognize(request: "RequestEnvelope", runtime: "SidecarRuntime") -> dict[str, Any]:
    image_handle = _require_str(request.params, "image_handle")
    _optional_object(request.params, "region")
    max_text_chars = _optional_int(request.params, "max_text_chars", default=4000, min_value=1)
    return _finish_long_task(
        request,
        runtime,
        task_type="ocr.recognize",
        owner="vision",
        progress_events=[("ocr.started", {"state": "started"})],
        terminal_event_type="ocr.done",
        summary={
            "image_handle": image_handle,
            "text": "识别文本示例"[:max_text_chars],
            "confidence": 1.0,
            "recognized": True,
        },
    )


def _handle_ocr_cleanup(request: "RequestEnvelope", runtime: "SidecarRuntime") -> dict[str, Any]:
    _optional_object(request.params, "policy")
    return {"cleanup_summary": {"released_handles": 0, "cleaned": True}}


def _handle_logs_query(request: "RequestEnvelope", runtime: "SidecarRuntime") -> dict[str, Any]:
    channel = _optional_str(request.params, "channel", default="all") or "all"
    limit = _optional_int(request.params, "limit", default=100, min_value=0, max_value=1000)
    _optional_str(request.params, "cursor", default=None)
    _optional_object(request.params, "filters")
    items = _log_items(runtime, channel, limit)
    return {"items": items, "next_cursor": None}


def _handle_logs_subscribe(request: "RequestEnvelope", runtime: "SidecarRuntime") -> dict[str, Any]:
    channel = _require_str(request.params, "channel")
    _optional_object(request.params, "filters")
    _optional_str(request.params, "cursor", default=None)
    items = _log_items(runtime, channel, 1)
    return _finish_long_task(
        request,
        runtime,
        task_type="logs.subscribe",
        owner="logs",
        progress_events=[("log.batch", {"items": items})],
        terminal_event_type="log.done",
        summary={"channel": channel, "item_count": len(items), "subscribed": True},
    )


def _handle_logs_export(request: "RequestEnvelope", runtime: "SidecarRuntime") -> dict[str, Any]:
    channel = _require_str(request.params, "channel")
    export_format = _require_str(request.params, "format")
    _optional_object(request.params, "filters")
    _optional_str(request.params, "confirm_token", default=None)
    return _finish_long_task(
        request,
        runtime,
        task_type="logs.export",
        owner="logs",
        progress_events=[("log.export_progress", {"progress": 1.0})],
        terminal_event_type="log.export_done",
        summary={
            "channel": channel,
            "format": export_format,
            "report_handle": _resource_handle("report", request.request_id),
            "exported": True,
        },
    )


def _handle_logs_open_location(request: "RequestEnvelope", runtime: "SidecarRuntime") -> dict[str, Any]:
    handle_id = _optional_str(request.params, "handle_id", default=None)
    report_id = _optional_str(request.params, "report_id", default=None)
    if not handle_id and not report_id:
        raise ServiceError(make_error("rpc.invalid_params", details={"field": "handle_id_or_report_id"}))
    return {"opened": False}


def _handle_tools_list(request: "RequestEnvelope", runtime: "SidecarRuntime") -> dict[str, Any]:
    include_disabled = _optional_bool(request.params, "include_disabled", default=False)
    items = _tool_items(runtime, include_disabled=include_disabled)
    if not items:
        items = [{"tool_name": DRY_RUN_TOOL_NAME, "enabled": True, "requires_confirmation": False}]
    if include_disabled:
        disabled_names = {item["tool_name"] for item in items if not item.get("enabled", True)}
        if DRY_RUN_DISABLED_TOOL_NAME not in disabled_names:
            items.append({"tool_name": DRY_RUN_DISABLED_TOOL_NAME, "enabled": False, "requires_confirmation": True})
    return {"items": items}


def _handle_tools_call(request: "RequestEnvelope", runtime: "SidecarRuntime") -> dict[str, Any]:
    tool_name = _require_str(request.params, "tool_name")
    source = _require_str(request.params, "source")
    arguments = _require_object(request.params, "arguments")
    dry_run = _optional_bool(request.params, "dry_run", default=False)
    confirm_token = _optional_str(request.params, "confirm_token", default=None)
    if not dry_run and not confirm_token:
        raise ServiceError(
            make_error(
                "tool.confirm_required",
                details={"tool_name": tool_name, "source_length": len(source), "capability": "tool.call"},
            )
        )
    return _finish_long_task(
        request,
        runtime,
        task_type="tools.call",
        owner="tools",
        progress_events=[
            ("tool.started", {"summary": {"tool_name": tool_name, "source_length": len(source), "dry_run": dry_run}}),
            ("tool.audit", {"audit_summary": {"tool_name": tool_name, "source_length": len(source), "dry_run": dry_run}}),
        ],
        terminal_event_type="tool.result",
        summary={
            "tool_name": tool_name,
            "source_length": len(source),
            "dry_run": dry_run,
            "argument_keys": sorted(str(key) for key in arguments),
            "executed": not dry_run,
        },
    )


def _handle_tools_audit_query(request: "RequestEnvelope", runtime: "SidecarRuntime") -> dict[str, Any]:
    limit = _optional_int(request.params, "limit", default=100, min_value=0, max_value=1000)
    _optional_str(request.params, "cursor", default=None)
    _optional_object(request.params, "filters")
    return {"items": _audit_items(limit), "next_cursor": None}


def _handle_plugins_refresh(request: "RequestEnvelope", runtime: "SidecarRuntime") -> dict[str, Any]:
    _optional_object(request.params, "filters")
    status = _plugin_status(None, runtime=runtime)
    return _finish_long_task(
        request,
        runtime,
        task_type="plugins.refresh",
        owner="plugins",
        progress_events=[("plugin.status", {"status": status})],
        terminal_event_type="plugin.done",
        summary={"plugin_count": len(_plugin_status_items(runtime)), "refreshed": True},
    )


def _handle_plugins_enable(request: "RequestEnvelope", runtime: "SidecarRuntime") -> dict[str, Any]:
    plugin_id = _require_str(request.params, "plugin_id")
    _require_token(request.params, "confirm_token")
    _publish(request, runtime, "plugin.status", {"status": _plugin_status(plugin_id, enabled=True, runtime=runtime)})
    return {"enabled": True}


def _handle_plugins_disable(request: "RequestEnvelope", runtime: "SidecarRuntime") -> dict[str, Any]:
    plugin_id = _require_str(request.params, "plugin_id")
    _publish(request, runtime, "plugin.status", {"status": _plugin_status(plugin_id, enabled=False, runtime=runtime)})
    return {"disabled": True}


def _handle_plugins_import(request: "RequestEnvelope", runtime: "SidecarRuntime") -> dict[str, Any]:
    package_handle = _require_str(request.params, "package_handle")
    _require_token(request.params, "confirm_token")
    return _finish_long_task(
        request,
        runtime,
        task_type="plugins.import",
        owner="plugins",
        progress_events=[("plugin.import_progress", {"progress": 1.0})],
        terminal_event_type="plugin.done",
        summary={"package_handle": package_handle, "imported": True},
    )


def _handle_plugins_status(request: "RequestEnvelope", runtime: "SidecarRuntime") -> dict[str, Any]:
    plugin_id = _optional_str(request.params, "plugin_id", default=None)
    return {"status": _plugin_status(plugin_id, runtime=runtime)}


def _handle_mcp_list_servers(request: "RequestEnvelope", runtime: "SidecarRuntime") -> dict[str, Any]:
    include_disabled = _optional_bool(request.params, "include_disabled", default=False)
    servers = _mcp_servers(runtime, include_disabled=include_disabled)
    return {"servers": servers}


def _handle_mcp_save_server(request: "RequestEnvelope", runtime: "SidecarRuntime") -> dict[str, Any]:
    draft = _require_object(request.params, "draft")
    version = _next_version(request.params)
    _require_token(request.params, "confirm_token")
    server_id = str(draft.get("server_id") or draft.get("name") or DEFAULT_MCP_SERVER_ID)
    _save_mcp_server_draft(runtime, {**draft, "name": server_id})
    summary = {"server_id": server_id, "enabled": bool(draft.get("enabled", True)), "saved": True}
    _publish(request, runtime, "mcp.config_changed", {"summary": summary})
    return {"applied_version": version, "server_summary": summary}


def _handle_mcp_refresh(request: "RequestEnvelope", runtime: "SidecarRuntime") -> dict[str, Any]:
    server_id = _optional_str(request.params, "server_id", default=None) or DEFAULT_MCP_SERVER_ID
    return _finish_long_task(
        request,
        runtime,
        task_type="mcp.refresh",
        owner="mcp",
        progress_events=[("mcp.status", {"status": {"server_id": server_id, "state": "refreshing"}})],
        terminal_event_type="mcp.done",
        summary={"server_id": server_id, "tool_count": _mcp_tool_count(runtime, server_id), "refreshed": True},
    )


def _handle_mcp_call_tool(request: "RequestEnvelope", runtime: "SidecarRuntime") -> dict[str, Any]:
    server_id = _require_str(request.params, "server_id")
    tool_name = _require_str(request.params, "tool_name")
    arguments = _require_object(request.params, "arguments")
    _optional_str(request.params, "confirm_token", default=None)
    return _finish_long_task(
        request,
        runtime,
        task_type="mcp.call_tool",
        owner="mcp",
        progress_events=[("mcp.tool_started", {"summary": {"server_id": server_id, "tool_name": tool_name}})],
        terminal_event_type="mcp.tool_done",
        summary={
            "server_id": server_id,
            "tool_name": tool_name,
            "argument_keys": sorted(str(key) for key in arguments),
            "executed": True,
        },
    )


def _handle_mcp_stop_server(request: "RequestEnvelope", runtime: "SidecarRuntime") -> dict[str, Any]:
    server_id = _require_str(request.params, "server_id")
    _optional_str(request.params, "reason", default="")
    _publish(request, runtime, "mcp.status", {"status": {"server_id": server_id, "state": "stopped"}})
    return {"stopped": True}


def _handle_security_approve(request: "RequestEnvelope", runtime: "SidecarRuntime") -> dict[str, Any]:
    confirmation_id = _require_str(request.params, "confirmation_id")
    _require_token(request.params, "confirm_token")
    _publish(request, runtime, "security.approved", {"confirmation_id": confirmation_id})
    return {"approved": True}


def _handle_security_deny(request: "RequestEnvelope", runtime: "SidecarRuntime") -> dict[str, Any]:
    confirmation_id = _require_str(request.params, "confirmation_id")
    _optional_str(request.params, "reason", default="")
    _publish(request, runtime, "security.denied", {"confirmation_id": confirmation_id})
    return {"denied": True}


def _handle_security_revoke_grant(request: "RequestEnvelope", runtime: "SidecarRuntime") -> dict[str, Any]:
    grant_id = _require_str(request.params, "grant_id")
    _publish(request, runtime, "security.grant_revoked", {"grant_id": grant_id})
    return {"revoked": True}


def _handle_security_list_grants(request: "RequestEnvelope", runtime: "SidecarRuntime") -> dict[str, Any]:
    _optional_object(request.params, "filters")
    return {"grants": [{"grant_id": DEFAULT_GRANT_ID, "capability": "diagnostics.view", "scope_hash": "dev-preview"}]}


def _handle_diagnostics_run(request: "RequestEnvelope", runtime: "SidecarRuntime") -> dict[str, Any]:
    checks = _require_array(request.params, "checks")
    include_sensitive = _optional_bool(request.params, "include_sensitive", default=False)
    if include_sensitive:
        raise ServiceError(make_error("security.permission_denied", details={"field": "include_sensitive"}))
    return _finish_long_task(
        request,
        runtime,
        task_type="diagnostics.run",
        owner="diagnostics",
        progress_events=[("diagnostic.progress", {"progress": 1.0})],
        terminal_event_type="diagnostic.done",
        summary={"check_count": len(checks), "passed": True, "report_handle": _resource_handle("report", request.request_id)},
    )


def _handle_diagnostics_export(request: "RequestEnvelope", runtime: "SidecarRuntime") -> dict[str, Any]:
    report_handle = _require_str(request.params, "report_handle")
    export_format = _require_str(request.params, "format")
    return _finish_long_task(
        request,
        runtime,
        task_type="diagnostics.export",
        owner="diagnostics",
        progress_events=[("diagnostic.export_progress", {"progress": 1.0})],
        terminal_event_type="diagnostic.done",
        summary={"report_handle": report_handle, "format": export_format, "export_handle": _resource_handle("report", request.request_id)},
    )


def _handle_diagnostics_open_report(request: "RequestEnvelope", runtime: "SidecarRuntime") -> dict[str, Any]:
    _require_str(request.params, "report_id")
    return {"opened": False}


def _handle_handles_read_range(request: "RequestEnvelope", runtime: "SidecarRuntime") -> dict[str, Any]:
    handle_id = _require_str(request.params, "handle_id")
    start = _require_int(request.params, "start", min_value=0)
    length = _require_int(request.params, "length", min_value=0, max_value=65536)
    text = f"resource content for {handle_id}"
    chunk = text[start : start + length]
    next_start = start + len(chunk) if start + len(chunk) < len(text) else None
    return {"chunk": chunk, "next_start": next_start}


def _handle_handles_read_page(request: "RequestEnvelope", runtime: "SidecarRuntime") -> dict[str, Any]:
    handle_id = _require_str(request.params, "handle_id")
    _optional_str(request.params, "page_token", default=None)
    limit = _optional_int(request.params, "limit", default=100, min_value=1, max_value=1000)
    return {"page": {"handle_id": handle_id, "items": [], "limit": limit}, "next_token": None}


def _handle_handles_release(request: "RequestEnvelope", runtime: "SidecarRuntime") -> dict[str, Any]:
    _require_str(request.params, "handle_id")
    return {"released": True}


def _handle_handles_stat(request: "RequestEnvelope", runtime: "SidecarRuntime") -> dict[str, Any]:
    _require_str(request.params, "handle_id")
    return {"kind": "resource", "byte_length": 0, "expires_at_ms": _now_ms() + 300000}


def _finish_chat(
    request: "RequestEnvelope",
    runtime: "SidecarRuntime",
    task_type: str,
    text: str,
    session_id: str,
    dry_run: bool,
) -> dict[str, Any]:
    response = "本地 dry-run 回复。" if dry_run else "Yumetsuki 已收到消息。"
    return _finish_long_task(
        request,
        runtime,
        task_type=task_type,
        owner="chat",
        progress_events=[
            ("chat.started", {"state": "started"}),
            ("chat.delta", {"text": response}),
        ],
        terminal_event_type="chat.done",
        summary={
            "message": response,
            "input_length": len(text),
            "session_id": session_id,
            "dry_run": dry_run,
            "fallback": not dry_run,
        },
    )


def _finish_long_task(
    request: "RequestEnvelope",
    runtime: "SidecarRuntime",
    task_type: str,
    owner: str,
    progress_events: list[tuple[str, dict[str, Any]]],
    terminal_event_type: str,
    summary: dict[str, Any],
    terminal_extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    context = _context(request)
    accepted = runtime.task_registry.accept_long_task(
        request_id=request.request_id,
        task_type=task_type,
        deadline_ms=request.deadline_ms,
        owner=owner,
        context=context,
    )
    publisher = runtime.task_registry.event_publisher
    for event_type, payload in progress_events:
        publisher.publish(event_type, context, payload)
    runtime.task_registry.mark_streaming(request.request_id)
    event = runtime.task_registry.publish_terminal_event(context, terminal_event_type, "done", summary=summary)
    if terminal_extra:
        event["payload"].update(terminal_extra)
    return accepted


def _publish(
    request: "RequestEnvelope",
    runtime: "SidecarRuntime",
    event_type: str,
    payload: dict[str, Any],
) -> None:
    runtime.task_registry.event_publisher.publish(event_type, _context(request), payload)


def _context(request: "RequestEnvelope") -> RpcContext:
    return RpcContext(
        request_id=request.request_id,
        trace_id=request.trace_id,
        parent_trace_id=request.parent_trace_id,
        session_id=request.session_id,
        deadline_ms=request.deadline_ms,
    )


def _config_snapshot(runtime: "SidecarRuntime", scope: str) -> dict[str, Any]:
    manager = _config_manager(runtime)
    api = manager.api
    system = manager.system
    memory = manager.memory
    agent = manager.agent
    mcp = manager.mcp
    return {
        "scope": scope,
        "api": {
            "provider": api.llm.provider,
            "base_url": _safe_url_summary(api.llm.base_url),
            "api_key": {"is_set": bool(api.llm.api_key), "mask": _mask_secret(api.llm.api_key)},
            "llm": {
                "provider": api.llm.provider,
                "model": api.llm.model,
                "stream": api.llm.stream,
                "temperature": api.llm.temperature,
                "max_tokens": api.llm.max_tokens,
            },
            "tts": {
                "engine": api.tts.engine,
                "audio_mode": api.tts.audio_mode,
                "reference_mode": api.tts.reference_mode,
                "api_url": _safe_url_summary(api.tts.api_url),
                "ref_audio_path": _path_summary(api.tts.ref_audio_path),
                "prompt_lang": api.tts.prompt_lang,
                "output_lang": api.tts.output_lang,
                "prompt_text_is_set": bool(api.tts.prompt_text),
            },
            "asr": {
                "engine": api.asr.engine,
                "model_path": _path_summary(api.asr.model_path),
                "device": api.asr.device,
                "compute_type": api.asr.compute_type,
                "language": api.asr.language,
                "transcribe_timeout_seconds": api.asr.transcribe_timeout_seconds,
            },
        },
        "system": {
            "runtime_mode": "headless-sidecar-facade",
            "platform": runtime.runtime_paths.platform,
            "theme": system.theme,
            "font_family": system.font_family,
            "font_size": system.font_size,
            "chat_display": system.chat_display.model_dump(),
            "passive_interaction": system.passive_interaction.model_dump(),
            "vision": {
                **system.vision.model_dump(),
                "screenshot_dir": _path_summary(system.vision.screenshot_dir),
            },
            "logging": {
                **system.logging.model_dump(),
                "log_root": _path_summary(system.logging.log_root),
            },
        },
        "memory": {
            "enabled": memory.enabled,
            "storage_dir": _path_summary(memory.storage_dir),
            "embedding_model_path": _path_summary(memory.embedding_model_path),
            "top_k": memory.top_k,
        },
        "agent": {
            "planner_enabled": agent.planner.llm_judge_enabled,
            "reflection_enabled": agent.reflector.enabled,
            "multi_step_enabled": agent.multi_step.enabled,
            "proactive_enabled": agent.proactive.enabled,
        },
        "mcp": {
            "servers": [
                {
                    "server_id": server.name,
                    "transport": server.transport,
                    "enabled": server.enabled,
                    "request_timeout_seconds": server.request_timeout_seconds,
                    "connect_timeout_seconds": server.connect_timeout_seconds,
                    "retry_attempts": server.retry_attempts,
                    "command_is_set": bool(server.command),
                    "url": _safe_url_summary(server.url),
                }
                for server in mcp.servers
            ],
        },
    }


def _config_manager(runtime: "SidecarRuntime"):
    from config.manager import ConfigManager

    return ConfigManager(runtime.runtime_paths.config_dir)


def _apply_config_draft(runtime: "SidecarRuntime", scope: str, draft: dict[str, Any]) -> None:
    manager = _config_manager(runtime)
    scoped = _scope_draft(scope, draft)
    if scope == "api":
        from config.schema import APIConfig

        data = manager.api.model_dump()
        llm_keys = {"provider", "model", "api_key", "base_url", "stream", "temperature", "max_tokens"}
        for key in llm_keys & set(scoped):
            data["llm"][key] = scoped[key]
        _deep_update(data, {key: value for key, value in scoped.items() if key not in llm_keys})
        manager.api = APIConfig(**data)
        manager.save_api()
        return
    if scope == "system":
        from config.schema import SystemConfig

        data = manager.system.model_dump()
        if "font_scale" in scoped:
            data.setdefault("chat_display", {})["font_scale"] = scoped["font_scale"]
        if "bubble_scale" in scoped:
            data.setdefault("chat_display", {})["bubble_scale"] = scoped["bubble_scale"]
        _deep_update(data, scoped)
        manager.system = SystemConfig(**data)
        manager.save_system()
        return
    if scope == "memory":
        from config.schema import MemoryConfig

        data = manager.memory.model_dump()
        _deep_update(data, scoped)
        manager.memory = MemoryConfig(**data)
        manager.save_memory()
        return
    if scope == "agent":
        from config.schema import AgentConfig

        data = manager.agent.model_dump()
        if "planner_enabled" in scoped:
            data.setdefault("planner", {})["llm_judge_enabled"] = scoped["planner_enabled"]
        if "reflection_enabled" in scoped:
            data.setdefault("reflector", {})["enabled"] = scoped["reflection_enabled"]
        _deep_update(data, scoped)
        manager.agent = AgentConfig(**data)
        manager.save_agent()
        return
    if scope == "mcp":
        from config.schema import MCPConfig

        data = manager.mcp.model_dump()
        _deep_update(data, scoped)
        manager.mcp = MCPConfig(**data)
        manager.save_mcp()
        return
    raise ServiceError(make_error("rpc.invalid_params", details={"field": "scope"}))


def _validate_config_draft(runtime: "SidecarRuntime", scope: str, draft: dict[str, Any]) -> dict[str, Any]:
    try:
        manager = _config_manager(runtime)
        scoped = _scope_draft(scope, draft)
        if scope == "api":
            from config.schema import APIConfig

            data = manager.api.model_dump()
            _deep_update(data, scoped)
            APIConfig(**data)
        elif scope == "system":
            from config.schema import SystemConfig

            data = manager.system.model_dump()
            _deep_update(data, scoped)
            SystemConfig(**data)
        elif scope == "memory":
            from config.schema import MemoryConfig

            data = manager.memory.model_dump()
            _deep_update(data, scoped)
            MemoryConfig(**data)
        elif scope == "agent":
            from config.schema import AgentConfig

            data = manager.agent.model_dump()
            _deep_update(data, scoped)
            AgentConfig(**data)
        elif scope == "mcp":
            from config.schema import MCPConfig

            data = manager.mcp.model_dump()
            _deep_update(data, scoped)
            MCPConfig(**data)
        else:
            raise ValueError(f"unknown scope: {scope}")
    except Exception as exc:  # noqa: BLE001 - validation reports shape errors as data.
        return {"ok": False, "issues": [{"summary": str(exc), "scope": scope}]}
    return {"ok": True, "issues": []}


def _scope_draft(scope: str, draft: dict[str, Any]) -> dict[str, Any]:
    value = draft.get(scope)
    if isinstance(value, dict):
        return value
    value = draft.get("redacted_snapshot")
    if isinstance(value, dict) and isinstance(value.get(scope), dict):
        return value[scope]
    return draft


def _deep_update(target: dict[str, Any], patch: dict[str, Any]) -> None:
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(target.get(key), dict):
            _deep_update(target[key], value)
            continue
        target[key] = value


def _character_summary(character_id: str, enabled: bool, display_name: str | None = None, root: Path | None = None) -> dict[str, Any]:
    return {
        "character_id": character_id,
        "display_name": display_name or character_id or "Yumetsuki",
        "enabled": enabled,
        "asset_summary": {
            "sprite_count": _sprite_count(root) if root else 0,
            "voice_count": 0,
        },
        "version": 1,
    }


def _character_detail(character_id: str, runtime: "SidecarRuntime") -> dict[str, Any]:
    root = _character_path(character_id, runtime)
    if root is None:
        return {
            **_character_summary(character_id, enabled=True),
            "persona": {"summary": "", "prompt_is_set": False},
            "paths": {"scoped": True, "values": []},
        }
    from core.character import load_character

    character = load_character(root)
    prompt_summary = _short_text(character.prompt or character.skill or character.soul)
    return {
        **_character_summary(character_id, enabled=True, display_name=character.name, root=root),
        "persona": {"summary": prompt_summary, "prompt_is_set": bool(character.prompt)},
        "emotions": [emotion.name for emotion in character.emotions],
        "paths": {"scoped": True, "values": [root.name]},
    }


def _character_items(runtime: "SidecarRuntime", include_disabled: bool) -> list[dict[str, Any]]:
    root = _characters_root(runtime)
    if root is None:
        return []
    items = []
    for path in sorted(item for item in root.iterdir() if item.is_dir()):
        detail = _character_detail(path.name, runtime)
        items.append({key: value for key, value in detail.items() if key in {"character_id", "display_name", "enabled", "asset_summary", "version"}})
    return items if include_disabled else [item for item in items if item.get("enabled", True)]


def _character_asset_count(character_id: str, runtime: "SidecarRuntime") -> int:
    root = _character_path(character_id, runtime)
    return _sprite_count(root) if root else 0


def _characters_root(runtime: "SidecarRuntime") -> Path | None:
    repo_root = Path(__file__).resolve().parents[2]
    candidates = [
        runtime.runtime_paths.resource_dir / "characters",
        repo_root / "data" / "characters",
    ]
    for candidate in candidates:
        if candidate.is_dir():
            return candidate
    return None


def _character_path(character_id: str, runtime: "SidecarRuntime") -> Path | None:
    root = _characters_root(runtime)
    if root is None:
        return None
    candidate = root / character_id
    if candidate.is_dir():
        return candidate
    return None


def _sprite_count(root: Path | None) -> int:
    if root is None:
        return 0
    sprite_root = root / "sprites"
    if not sprite_root.is_dir():
        return 0
    return sum(1 for path in sprite_root.iterdir() if path.is_file())


def _log_items(runtime: "SidecarRuntime", channel: str, limit: int) -> list[dict[str, Any]]:
    if limit == 0:
        return []
    items: list[dict[str, Any]] = []
    for path in _log_files(runtime, channel):
        try:
            lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError:
            continue
        for index, line in enumerate(lines, start=1):
            if not line.strip():
                continue
            try:
                raw = json.loads(line)
            except json.JSONDecodeError:
                continue
            items.append(_log_item_from_raw(raw, path, index, channel))
    items.sort(key=lambda item: item.get("timestamp_ms", 0), reverse=True)
    return items[:limit]


def _log_files(runtime: "SidecarRuntime", channel: str) -> list[Path]:
    root = runtime.runtime_paths.log_dir
    folders = []
    if channel in {"all", "system"}:
        folders.append(root / "system")
    if channel in {"all", "conversation"}:
        folders.append(root / "conversation")
    files: list[Path] = []
    for folder in folders:
        if folder.is_dir():
            files.extend(path for path in folder.glob("*.jsonl") if path.is_file())
    return sorted(files, key=lambda path: path.stat().st_mtime if path.exists() else 0, reverse=True)


def _log_item_from_raw(raw: dict[str, Any], path: Path, line_no: int, fallback_channel: str) -> dict[str, Any]:
    timestamp_ms = raw.get("timestamp_ms")
    if not isinstance(timestamp_ms, int):
        timestamp_ms = _now_ms()
    return {
        "entry_id": str(raw.get("entry_id") or f"{path.stem}:{line_no}"),
        "timestamp_ms": timestamp_ms,
        "channel": str(raw.get("channel") or fallback_channel),
        "level": str(raw.get("level") or "info"),
        "message": str(raw.get("message") or raw.get("summary") or raw.get("event_type") or ""),
        "source": str(raw.get("source") or "python_core"),
        "trace_id": str(raw.get("trace_id") or ""),
    }


def _audit_items(limit: int) -> list[dict[str, Any]]:
    if limit == 0:
        return []
    return [
        {
            "audit_entry_id": "dryrun-audit-1",
            "timestamp_ms": _now_ms(),
            "actor": "sidecar",
            "action": "dry_run",
            "allowed": True,
            "tool_name": DRY_RUN_TOOL_NAME,
        }
    ][:limit]


def _tool_items(runtime: "SidecarRuntime", include_disabled: bool) -> list[dict[str, Any]]:
    try:
        host = _plugin_host(runtime)
        specs = host.tool_specs()
    except Exception:
        specs = []
    items = []
    for spec in specs:
        function = spec.get("function", {})
        name = str(function.get("name") or "")
        if not name:
            continue
        items.append(
            {
                "tool_name": name,
                "enabled": True,
                "requires_confirmation": _tool_requires_confirmation(name),
                "description": str(function.get("description") or ""),
            }
        )
    return items if include_disabled else [item for item in items if item["enabled"]]


def _tool_requires_confirmation(tool_name: str) -> bool:
    return any(part in tool_name for part in ("run_command", "open_file", "open_url", "web_session"))


def _plugin_host(runtime: "SidecarRuntime"):
    from core.plugin_host import PluginHost

    repo_root = Path(__file__).resolve().parents[2]
    host = PluginHost(repo_root / "plugins")
    host.load()
    return host


def _plugin_status_items(runtime: "SidecarRuntime") -> list[dict[str, Any]]:
    try:
        host = _plugin_host(runtime)
    except Exception:
        return []
    return [
        {
            "plugin_id": status.name,
            "enabled": status.loaded,
            "loaded": status.loaded,
            "worker_state": "idle" if status.loaded else "failed",
            "tool_count": status.tools_count,
            "description": status.description,
            "message": status.message,
        }
        for status in host.statuses
    ]


def _plugin_status(
    plugin_id: str | None,
    enabled: bool = True,
    runtime: "SidecarRuntime" | None = None,
) -> dict[str, Any]:
    items = _plugin_status_items(runtime) if runtime is not None else []
    target = plugin_id or (items[0]["plugin_id"] if items else DEFAULT_PLUGIN_ID)
    for item in items:
        if item["plugin_id"] == target:
            return {**item, "enabled": enabled}
    return {
        "plugin_id": target,
        "enabled": enabled,
        "loaded": False,
        "worker_state": "not_found",
        "tool_count": 0,
    }


def _mcp_servers(runtime: "SidecarRuntime", include_disabled: bool) -> list[dict[str, Any]]:
    manager = _config_manager(runtime)
    items = []
    for server in manager.mcp.servers:
        if not include_disabled and not server.enabled:
            continue
        items.append(
            {
                "server_id": server.name,
                "enabled": server.enabled,
                "state": "configured" if server.enabled else "disabled",
                "transport": server.transport,
                "tool_count": 0,
            }
        )
    return items


def _save_mcp_server_draft(runtime: "SidecarRuntime", draft: dict[str, Any]) -> None:
    from config.schema import MCPConfig

    manager = _config_manager(runtime)
    data = manager.mcp.model_dump()
    servers = list(data.get("servers") or [])
    name = str(draft.get("name") or DEFAULT_MCP_SERVER_ID)
    patch = {
        "name": name,
        "transport": str(draft.get("transport") or "stdio"),
        "command": str(draft.get("command") or ""),
        "url": str(draft.get("url") or ""),
        "enabled": bool(draft.get("enabled", True)),
        "connect_timeout_seconds": int(draft.get("connect_timeout_seconds") or 10),
        "request_timeout_seconds": int(draft.get("request_timeout_seconds") or 10),
        "retry_attempts": int(draft.get("retry_attempts") or 0),
    }
    replaced = False
    for index, item in enumerate(servers):
        if item.get("name") == name:
            servers[index] = {**item, **patch}
            replaced = True
            break
    if not replaced:
        servers.append(patch)
    manager.mcp = MCPConfig(servers=servers)
    manager.save_mcp()


def _mcp_tool_count(runtime: "SidecarRuntime", server_id: str) -> int:
    return next((server["tool_count"] for server in _mcp_servers(runtime, include_disabled=True) if server["server_id"] == server_id), 0)


def _safe_url_summary(value: str) -> str | None:
    if not value:
        return None
    if "@" in value:
        return value.split("@", 1)[-1]
    return value


def _mask_secret(value: str) -> str | None:
    if not value:
        return None
    if len(value) <= 6:
        return "***"
    return f"{value[:2]}***{value[-2:]}"


def _path_summary(value: str) -> str | None:
    if not value:
        return None
    return Path(value).name or "***"


def _short_text(value: str, limit: int = 120) -> str:
    normalized = " ".join(value.split())
    if len(normalized) <= limit:
        return normalized
    return normalized[:limit] + "..."


def _next_version(params: dict[str, Any]) -> int:
    return _require_int(params, "base_version", min_value=0) + 1


def _require_token(params: dict[str, Any], field: str) -> str:
    value = _require_str(params, field)
    if value == "<redacted>":
        raise ServiceError(make_error("security.confirm_token_invalid", details={"field": field}))
    return value


def _require_str(params: dict[str, Any], field: str) -> str:
    value = params.get(field)
    if not isinstance(value, str) or not value:
        raise ServiceError(make_error("rpc.invalid_params", details={"field": field}))
    return value


def _optional_str(params: dict[str, Any], field: str, default: str | None) -> str | None:
    if field not in params or params[field] is None:
        return default
    value = params[field]
    if not isinstance(value, str):
        raise ServiceError(make_error("rpc.invalid_params", details={"field": field}))
    return value


def _require_bool(params: dict[str, Any], field: str) -> bool:
    value = params.get(field)
    if not isinstance(value, bool):
        raise ServiceError(make_error("rpc.invalid_params", details={"field": field}))
    return value


def _optional_bool(params: dict[str, Any], field: str, default: bool) -> bool:
    if field not in params:
        return default
    value = params[field]
    if not isinstance(value, bool):
        raise ServiceError(make_error("rpc.invalid_params", details={"field": field}))
    return value


def _require_int(
    params: dict[str, Any],
    field: str,
    min_value: int | None = None,
    max_value: int | None = None,
) -> int:
    value = params.get(field)
    if type(value) is not int:
        raise ServiceError(make_error("rpc.invalid_params", details={"field": field}))
    if min_value is not None and value < min_value:
        raise ServiceError(make_error("rpc.invalid_params", details={"field": field, "min": min_value}))
    if max_value is not None and value > max_value:
        raise ServiceError(make_error("rpc.invalid_params", details={"field": field, "max": max_value}))
    return value


def _optional_int(
    params: dict[str, Any],
    field: str,
    default: int,
    min_value: int | None = None,
    max_value: int | None = None,
) -> int:
    if field not in params:
        return default
    return _require_int(params, field, min_value=min_value, max_value=max_value)


def _require_object(params: dict[str, Any], field: str) -> dict[str, Any]:
    value = params.get(field)
    if not isinstance(value, dict):
        raise ServiceError(make_error("rpc.invalid_params", details={"field": field}))
    return value


def _optional_object(params: dict[str, Any], field: str) -> dict[str, Any] | None:
    if field not in params or params[field] is None:
        return None
    return _require_object(params, field)


def _require_array(params: dict[str, Any], field: str) -> list[Any]:
    value = params.get(field)
    if not isinstance(value, list):
        raise ServiceError(make_error("rpc.invalid_params", details={"field": field}))
    return value


def _resource_handle(kind: str, request_id: str) -> str:
    return f"handle:{kind}:{request_id}"


def _now_ms() -> int:
    return int(time.time() * 1000)
