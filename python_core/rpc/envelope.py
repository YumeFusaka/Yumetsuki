from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from .errors import RpcError, contains_unredacted_sensitive_value


TerminalState = Literal["done", "error", "cancelled"]


class RpcValidationError(ValueError):
    pass


@dataclass(frozen=True)
class RequestEnvelope:
    kind: Literal["request"]
    request_id: str
    method: str
    params: dict[str, Any]
    protocol_version: int
    trace_id: str
    parent_trace_id: str | None
    session_id: str
    deadline_ms: int


@dataclass(frozen=True)
class ResponseEnvelope:
    kind: Literal["response"]
    request_id: str
    ok: bool
    result: dict[str, Any] | None
    error: RpcError | None
    protocol_version: int
    trace_id: str
    parent_trace_id: str | None
    session_id: str


@dataclass(frozen=True)
class EventEnvelope:
    kind: Literal["event"]
    type: str
    request_id: str
    protocol_version: int
    trace_id: str
    parent_trace_id: str | None
    session_id: str
    sequence: int
    timestamp_ms: int
    payload: dict[str, Any]


def validate_no_legacy_id(payload: dict[str, Any]) -> None:
    def walk(value: Any, path: str) -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                if key == "id":
                    raise RpcValidationError(f"legacy id field is forbidden at {path}.id")
                walk(item, f"{path}.{key}")
        elif isinstance(value, list):
            for index, item in enumerate(value):
                walk(item, f"{path}[{index}]")

    walk(payload, "$")


def validate_request_envelope(payload: dict[str, Any]) -> RequestEnvelope:
    validate_no_legacy_id(payload)
    _require_kind(payload, "request")
    _require_fields(
        payload,
        {
            "request_id": str,
            "method": str,
            "params": dict,
            "protocol_version": int,
            "trace_id": str,
            "parent_trace_id": (str, type(None)),
            "session_id": str,
            "deadline_ms": int,
        },
    )
    return RequestEnvelope(
        kind="request",
        request_id=payload["request_id"],
        method=payload["method"],
        params=payload["params"],
        protocol_version=payload["protocol_version"],
        trace_id=payload["trace_id"],
        parent_trace_id=payload["parent_trace_id"],
        session_id=payload["session_id"],
        deadline_ms=payload["deadline_ms"],
    )


def validate_response_envelope(payload: dict[str, Any]) -> ResponseEnvelope:
    validate_no_legacy_id(payload)
    _require_kind(payload, "response")
    _require_fields(
        payload,
        {
            "request_id": str,
            "ok": bool,
            "protocol_version": int,
            "trace_id": str,
            "parent_trace_id": (str, type(None)),
            "session_id": str,
        },
    )
    if "result" not in payload or "error" not in payload:
        raise RpcValidationError("response requires result and error fields")
    if payload["ok"]:
        if not isinstance(payload["result"], dict) or payload["error"] is not None:
            raise RpcValidationError("ok response requires object result and null error")
        error = None
    else:
        if payload["result"] is not None or not isinstance(payload["error"], dict):
            raise RpcValidationError("error response requires null result and object error")
        error = validate_rpc_error(payload["error"])
    return ResponseEnvelope(
        kind="response",
        request_id=payload["request_id"],
        ok=payload["ok"],
        result=payload["result"],
        error=error,
        protocol_version=payload["protocol_version"],
        trace_id=payload["trace_id"],
        parent_trace_id=payload["parent_trace_id"],
        session_id=payload["session_id"],
    )


def validate_event_envelope(payload: dict[str, Any]) -> EventEnvelope:
    validate_no_legacy_id(payload)
    _require_kind(payload, "event")
    _require_fields(
        payload,
        {
            "type": str,
            "request_id": str,
            "protocol_version": int,
            "trace_id": str,
            "parent_trace_id": (str, type(None)),
            "session_id": str,
            "sequence": int,
            "timestamp_ms": int,
            "payload": dict,
        },
    )
    state = payload["payload"].get("terminal_state") or payload["payload"].get("state")
    if state == "timeout":
        raise RpcValidationError("timeout is not a terminal state")
    if state in ("done", "error", "cancelled"):
        if "summary" not in payload["payload"]:
            raise RpcValidationError("terminal event requires summary")
    if payload["type"].endswith((".done", ".error", ".cancelled")) or state in ("done", "error", "cancelled"):
        if state not in ("done", "error", "cancelled"):
            raise RpcValidationError("terminal event requires done/error/cancelled state")
    if (payload["type"].endswith(".error") or state == "error") and isinstance(payload["payload"].get("error"), dict):
        validate_rpc_error(payload["payload"]["error"])
    return EventEnvelope(
        kind="event",
        type=payload["type"],
        request_id=payload["request_id"],
        protocol_version=payload["protocol_version"],
        trace_id=payload["trace_id"],
        parent_trace_id=payload["parent_trace_id"],
        session_id=payload["session_id"],
        sequence=payload["sequence"],
        timestamp_ms=payload["timestamp_ms"],
        payload=payload["payload"],
    )


def validate_rpc_error(payload: dict[str, Any]) -> RpcError:
    _require_fields(
        payload,
        {
            "code": str,
            "message": str,
            "user_message": str,
            "retryable": bool,
            "details": dict,
        },
    )
    if contains_unredacted_sensitive_value(payload["details"]):
        raise RpcValidationError("rpc error details contain unredacted sensitive data")
    return RpcError(
        code=payload["code"],
        message=payload["message"],
        user_message=payload["user_message"],
        retryable=payload["retryable"],
        details=payload["details"],
    )


def response_payload(
    request: RequestEnvelope,
    result: dict[str, Any] | None = None,
    error: RpcError | None = None,
) -> dict[str, Any]:
    ok = error is None
    return {
        "kind": "response",
        "request_id": request.request_id,
        "ok": ok,
        "result": result if ok else None,
        "error": None if ok else error.to_dict(),
        "protocol_version": request.protocol_version,
        "trace_id": request.trace_id,
        "parent_trace_id": request.parent_trace_id,
        "session_id": request.session_id,
    }


def event_payload(event: EventEnvelope) -> dict[str, Any]:
    return {
        "kind": "event",
        "type": event.type,
        "request_id": event.request_id,
        "protocol_version": event.protocol_version,
        "trace_id": event.trace_id,
        "parent_trace_id": event.parent_trace_id,
        "session_id": event.session_id,
        "sequence": event.sequence,
        "timestamp_ms": event.timestamp_ms,
        "payload": event.payload,
    }


def _require_kind(payload: dict[str, Any], kind: str) -> None:
    if payload.get("kind") != kind:
        raise RpcValidationError(f"expected kind={kind}")


def _require_fields(payload: dict[str, Any], schema: dict[str, Any]) -> None:
    for key, expected_type in schema.items():
        if key not in payload:
            raise RpcValidationError(f"missing required field: {key}")
        if not isinstance(payload[key], expected_type):
            raise RpcValidationError(f"field {key} has invalid type")
