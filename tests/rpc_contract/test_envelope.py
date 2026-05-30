from __future__ import annotations

import pytest

from python_core.rpc.envelope import (
    assert_event_sequence,
    validate_event_envelope,
    validate_no_legacy_id,
    validate_request_envelope,
    validate_response_envelope,
    validate_rpc_error,
)


BASE = {
    "protocol_version": 1,
    "request_id": "req_1",
    "trace_id": "trace_1",
    "parent_trace_id": None,
    "session_id": "sess_1",
}


def test_valid_request_envelope() -> None:
    request = validate_request_envelope(
        {
            **BASE,
            "kind": "request",
            "method": "config.get_all",
            "params": {},
            "deadline_ms": 30000,
        }
    )
    assert request.method == "config.get_all"


def test_request_missing_canonical_field_fails() -> None:
    payload = {**BASE, "kind": "request", "method": "config.get_all", "params": {}}
    with pytest.raises(ValueError, match="deadline_ms"):
        validate_request_envelope(payload)


def test_valid_success_and_error_response() -> None:
    success = validate_response_envelope(
        {**BASE, "kind": "response", "ok": True, "result": {"ready": True}, "error": None}
    )
    assert success.ok is True

    error = validate_response_envelope(
        {
            **BASE,
            "kind": "response",
            "ok": False,
            "result": None,
            "error": {
                "code": "sidecar.not_ready",
                "message": "not ready",
                "user_message": "尚未就绪",
                "retryable": True,
                "details": {"stage": "startup"},
            },
        }
    )
    assert error.error is not None
    assert error.error.code == "sidecar.not_ready"


def test_response_ok_result_error_are_mutually_exclusive() -> None:
    with pytest.raises(ValueError, match="error=null"):
        validate_response_envelope(
            {**BASE, "kind": "response", "ok": True, "result": {}, "error": {"code": "rpc.invalid_params"}}
        )
    with pytest.raises(ValueError, match="result=null"):
        validate_response_envelope(
            {**BASE, "kind": "response", "ok": False, "result": {}, "error": {"code": "rpc.invalid_params"}}
        )


def test_valid_event_and_sequence_check() -> None:
    first = validate_event_envelope(
        {
            **BASE,
            "kind": "event",
            "type": "chat.delta",
            "sequence": 1,
            "timestamp_ms": 1779970000000,
            "payload": {"text": "hello"},
        }
    )
    second = validate_event_envelope({**first.__dict__, "kind": "event", "sequence": 2})
    assert_event_sequence(first.sequence, second)
    with pytest.raises(ValueError, match="sequence"):
        assert_event_sequence(second.sequence, first)


def test_event_terminal_state_rules() -> None:
    with pytest.raises(ValueError, match="timeout"):
        validate_event_envelope(
            {
                **BASE,
                "kind": "event",
                "type": "chat.error",
                "sequence": 1,
                "timestamp_ms": 1779970000000,
                "payload": {"state": "timeout"},
            }
        )
    with pytest.raises(ValueError, match="terminal state"):
        validate_event_envelope(
            {
                **BASE,
                "kind": "event",
                "type": "chat.done",
                "sequence": 1,
                "timestamp_ms": 1779970000000,
                "payload": {"state": "running"},
            }
        )


def test_rpc_error_rejects_unredacted_details() -> None:
    with pytest.raises(ValueError, match="unredacted"):
        validate_rpc_error(
            {
                "code": "rpc.invalid_params",
                "message": "bad",
                "user_message": "参数错误",
                "retryable": False,
                "details": {"authorization": "Bearer secret"},
            }
        )


def test_legacy_id_field_is_forbidden() -> None:
    with pytest.raises(ValueError, match="legacy id"):
        validate_no_legacy_id({"id": "old"})
