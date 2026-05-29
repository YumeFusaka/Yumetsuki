from __future__ import annotations

import pytest

from python_core.rpc.envelope import (
    RpcValidationError,
    validate_event_envelope,
    validate_no_legacy_id,
    validate_request_envelope,
    validate_response_envelope,
    validate_rpc_error,
)
from python_core.rpc.errors import make_error


def request_payload() -> dict[str, object]:
    return {
        "kind": "request",
        "request_id": "req_1",
        "method": "config.get_all",
        "params": {},
        "protocol_version": 1,
        "trace_id": "trace_1",
        "parent_trace_id": None,
        "session_id": "sess_1",
        "deadline_ms": 30000,
    }


def test_request_response_event_envelopes_validate() -> None:
    request = validate_request_envelope(request_payload())
    assert request.request_id == "req_1"

    success = {
        "kind": "response",
        "request_id": "req_1",
        "ok": True,
        "result": {"value": 1},
        "error": None,
        "protocol_version": 1,
        "trace_id": "trace_1",
        "parent_trace_id": None,
        "session_id": "sess_1",
    }
    assert validate_response_envelope(success).ok is True

    error_response = success | {
        "ok": False,
        "result": None,
        "error": make_error("rpc.invalid_params", details={"field": "params"}).to_dict(),
    }
    assert validate_response_envelope(error_response).error is not None

    event = {
        "kind": "event",
        "type": "chat.delta",
        "request_id": "req_1",
        "protocol_version": 1,
        "trace_id": "trace_1",
        "parent_trace_id": None,
        "session_id": "sess_1",
        "sequence": 1,
        "timestamp_ms": 1779970000000,
        "payload": {"text": "hello"},
    }
    assert validate_event_envelope(event).sequence == 1


@pytest.mark.parametrize("missing", ["request_id", "method", "params", "deadline_ms"])
def test_request_requires_canonical_fields(missing: str) -> None:
    payload = request_payload()
    payload.pop(missing)
    with pytest.raises(RpcValidationError):
        validate_request_envelope(payload)


def test_response_result_error_are_mutually_exclusive() -> None:
    payload = {
        "kind": "response",
        "request_id": "req_1",
        "ok": True,
        "result": {"value": 1},
        "error": make_error("rpc.invalid_params").to_dict(),
        "protocol_version": 1,
        "trace_id": "trace_1",
        "parent_trace_id": None,
        "session_id": "sess_1",
    }
    with pytest.raises(RpcValidationError):
        validate_response_envelope(payload)


def test_error_details_must_be_redacted() -> None:
    with pytest.raises(RpcValidationError):
        validate_rpc_error(
            {
                "code": "rpc.invalid_params",
                "message": "bad",
                "user_message": "bad",
                "retryable": False,
                "details": {"api_key": "sk-secret-token-value"},
            }
        )


def test_legacy_id_field_is_forbidden() -> None:
    with pytest.raises(RpcValidationError):
        validate_no_legacy_id({"kind": "request", "id": "legacy"})


def test_timeout_is_not_terminal_state() -> None:
    event = {
        "kind": "event",
        "type": "chat.error",
        "request_id": "req_1",
        "protocol_version": 1,
        "trace_id": "trace_1",
        "parent_trace_id": None,
        "session_id": "sess_1",
        "sequence": 1,
        "timestamp_ms": 1779970000000,
        "payload": {"terminal_state": "timeout"},
    }
    with pytest.raises(RpcValidationError):
        validate_event_envelope(event)
