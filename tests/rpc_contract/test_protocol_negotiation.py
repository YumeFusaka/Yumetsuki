from __future__ import annotations

from python_core.runtime_paths import RuntimePaths
from python_core.rpc.envelope import validate_request_envelope
from python_core.rpc.registry import SidecarRuntime, build_default_registry


def request(supported_versions: list[int]) -> dict[str, object]:
    return {
        "kind": "request",
        "request_id": "req_proto",
        "method": "sidecar.hello",
        "params": {"supported_protocol_versions": supported_versions},
        "protocol_version": 1,
        "trace_id": "trace_proto",
        "parent_trace_id": None,
        "session_id": "sess_proto",
        "deadline_ms": 30000,
    }


def test_protocol_negotiation_selects_v1_when_supported() -> None:
    registry = build_default_registry()
    runtime = SidecarRuntime.create(RuntimePaths.temporary())
    response = registry.dispatch(validate_request_envelope(request([1, 2])), runtime)
    assert response["ok"] is True
    assert response["result"]["selected_protocol_version"] == 1
    assert response["result"]["min_compatible_protocol_version"] == 1


def test_protocol_negotiation_rejects_unsupported_versions() -> None:
    registry = build_default_registry()
    runtime = SidecarRuntime.create(RuntimePaths.temporary())
    response = registry.dispatch(validate_request_envelope(request([99])), runtime)
    assert response["ok"] is False
    assert response["error"]["code"] == "rpc.protocol_unsupported"
