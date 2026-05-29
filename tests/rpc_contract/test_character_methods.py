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
            "trace_id": "trace_character",
            "parent_trace_id": None,
            "session_id": "sess_character",
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


def test_character_read_methods_return_safe_defaults() -> None:
    harness = RpcHarness()

    list_response, _list_events = harness.dispatch("character.list", {"include_disabled": True})
    get_response, _get_events = harness.dispatch("character.get", {"character_id": "default"})
    protect_response, _protect_events = harness.dispatch("character.protect_core_files", {"character_id": "default"})

    assert list_response["ok"] is True
    assert list_response["result"]["items"]
    assert "character_id" in list_response["result"]["items"][0]
    assert get_response["result"]["redacted_character"]["paths"]["scoped"] is True
    assert protect_response["result"]["protection_summary"]["protected"] is True


def test_character_write_methods_publish_changed_events() -> None:
    harness = RpcHarness()

    save_response, save_events = harness.dispatch(
        "character.save",
        {"draft": {"character_id": "custom"}, "base_version": 1, "confirm_token": "confirm"},
    )
    delete_response, delete_events = harness.dispatch(
        "character.delete",
        {"character_id": "custom", "confirm_token": "confirm"},
    )

    assert save_response["ok"] is True
    assert save_response["result"]["applied_version"] == 2
    assert save_events[-1]["type"] == "character.changed"
    assert delete_response["result"]["deleted"] is True
    assert delete_events[-1]["type"] == "character.changed"


def test_character_sync_assets_is_accepted_and_emits_single_terminal_event() -> None:
    response, events = RpcHarness().dispatch(
        "character.sync_assets",
        {"character_id": "default", "asset_handles": ["handle:image:asset"]},
    )

    assert response["ok"] is True
    assert response["result"]["status"] == "accepted"
    assert response["result"]["task_type"] == "character.sync_assets"
    assert [event["type"] for event in events] == ["character.assets_progress", "character.assets_done"]
    assert len(_terminal_events(events)) == 1


def test_character_missing_required_field_is_invalid_params() -> None:
    response, _events = RpcHarness().dispatch("character.get", {})

    assert response["ok"] is False
    assert response["error"]["code"] == "rpc.invalid_params"
