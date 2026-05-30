from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from .errors import RpcError, assert_details_are_redacted


TerminalState = Literal["done", "error", "cancelled"]
COMMON_FIELDS = {
    "protocol_version": int,
    "request_id": str,
    "trace_id": str,
    "session_id": str,
}


@dataclass(frozen=True)
class RequestEnvelope:
    protocol_version: int
    request_id: str
    trace_id: str
    parent_trace_id: str | None
    session_id: str
    method: str
    params: dict[str, Any]
    deadline_ms: int


@dataclass(frozen=True)
class ResponseEnvelope:
    protocol_version: int
    request_id: str
    trace_id: str
    parent_trace_id: str | None
    session_id: str
    ok: bool
    result: dict[str, Any] | None
    error: RpcError | None


@dataclass(frozen=True)
class EventEnvelope:
    protocol_version: int
    request_id: str
    trace_id: str
    parent_trace_id: str | None
    session_id: str
    type: str
    sequence: int
    timestamp_ms: int
    payload: dict[str, Any]


def validate_no_legacy_id(payload: dict[str, Any]) -> None:
    def visit(value: Any, path: str) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                if key == "id":
                    raise ValueError(f"legacy id field is forbidden at {path}.id")
                visit(child, f"{path}.{key}")
        elif isinstance(value, list):
            for index, child in enumerate(value):
                visit(child, f"{path}[{index}]")

    visit(payload, "$")


def validate_request_envelope(payload: dict[str, Any]) -> RequestEnvelope:
    _validate_kind(payload, "request")
    _validate_common(payload)
    _require_type(payload, "method", str)
    _require_type(payload, "params", dict)
    _require_type(payload, "deadline_ms", int)
    return RequestEnvelope(
        protocol_version=payload["protocol_version"],
        request_id=payload["request_id"],
        trace_id=payload["trace_id"],
        parent_trace_id=payload["parent_trace_id"],
        session_id=payload["session_id"],
        method=payload["method"],
        params=payload["params"],
        deadline_ms=payload["deadline_ms"],
    )


def validate_response_envelope(payload: dict[str, Any]) -> ResponseEnvelope:
    _validate_kind(payload, "response")
    _validate_common(payload)
    _require_type(payload, "ok", bool)
    if "result" not in payload or "error" not in payload:
        raise ValueError("response requires result and error")
    error = None
    result = payload["result"]
    if payload["ok"] is True:
        if payload["error"] is not None:
            raise ValueError("ok response must have error=null")
        if not isinstance(result, dict):
            raise ValueError("ok response requires object result")
    else:
        if result is not None:
            raise ValueError("error response must have result=null")
        if not isinstance(payload["error"], dict):
            raise ValueError("error response requires RpcError")
        error = validate_rpc_error(payload["error"])
    return ResponseEnvelope(
        protocol_version=payload["protocol_version"],
        request_id=payload["request_id"],
        trace_id=payload["trace_id"],
        parent_trace_id=payload["parent_trace_id"],
        session_id=payload["session_id"],
        ok=payload["ok"],
        result=result,
        error=error,
    )


def validate_event_envelope(payload: dict[str, Any]) -> EventEnvelope:
    _validate_kind(payload, "event")
    _validate_common(payload)
    _require_type(payload, "type", str)
    _require_type(payload, "sequence", int)
    _require_type(payload, "timestamp_ms", int)
    _require_type(payload, "payload", dict)
    state = payload["payload"].get("state")
    if state == "timeout":
        raise ValueError("timeout is not a terminal state")
    if state is not None and payload["type"].endswith((".done", ".error", ".cancelled")):
        if state not in ("done", "error", "cancelled"):
            raise ValueError("invalid terminal state")
    if payload["type"].endswith(".error") and "error" in payload["payload"]:
        validate_rpc_error(payload["payload"]["error"])
    return EventEnvelope(
        protocol_version=payload["protocol_version"],
        request_id=payload["request_id"],
        trace_id=payload["trace_id"],
        parent_trace_id=payload["parent_trace_id"],
        session_id=payload["session_id"],
        type=payload["type"],
        sequence=payload["sequence"],
        timestamp_ms=payload["timestamp_ms"],
        payload=payload["payload"],
    )


def validate_rpc_error(payload: dict[str, Any]) -> RpcError:
    _require_type(payload, "code", str)
    _require_type(payload, "message", str)
    _require_type(payload, "user_message", str)
    _require_type(payload, "retryable", bool)
    _require_type(payload, "details", dict)
    assert_details_are_redacted(payload["details"])
    return RpcError(
        code=payload["code"],
        message=payload["message"],
        user_message=payload["user_message"],
        retryable=payload["retryable"],
        details=payload["details"],
    )


def assert_event_sequence(previous_sequence: int | None, event: EventEnvelope) -> None:
    if previous_sequence is not None and event.sequence <= previous_sequence:
        raise ValueError("event sequence must increase within request")


def _validate_kind(payload: dict[str, Any], expected: str) -> None:
    validate_no_legacy_id(payload)
    _require_type(payload, "kind", str)
    if payload["kind"] != expected:
        raise ValueError(f"expected kind={expected}")


def _validate_common(payload: dict[str, Any]) -> None:
    for field, expected_type in COMMON_FIELDS.items():
        _require_type(payload, field, expected_type)
    if "parent_trace_id" not in payload:
        raise ValueError("missing parent_trace_id")
    if payload["parent_trace_id"] is not None and not isinstance(payload["parent_trace_id"], str):
        raise TypeError("parent_trace_id must be string or null")


def _require_type(payload: dict[str, Any], field: str, expected_type: type) -> None:
    if field not in payload:
        raise ValueError(f"missing {field}")
    if not isinstance(payload[field], expected_type):
        raise TypeError(f"{field} must be {expected_type.__name__}")
