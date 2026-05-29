from __future__ import annotations

from typing import Any

from python_core.rpc.errors import ERROR_CATALOG
from python_core.rpc.schema.schema_hash import load_catalog


class CatalogValidationError(ValueError):
    pass


def validate_catalog(catalog: dict[str, Any] | None = None) -> None:
    payload = catalog or load_catalog()
    _require_top_level(payload)
    methods = payload["methods"]
    events = payload["events"]
    method_names = [method["method"] for method in methods]
    event_types = {event["type"] for event in events}

    if len(method_names) != len(set(method_names)):
        raise CatalogValidationError("duplicate method in catalog")
    if "security.confirm_required" in method_names:
        raise CatalogValidationError("security.confirm_required must be event-only")
    cancel_like = [
        name
        for name in method_names
        if name != "sidecar.cancel" and (name.endswith(".cancel") or name.startswith("cancel_"))
    ]
    if cancel_like:
        raise CatalogValidationError(f"cancel wire methods are forbidden: {cancel_like}")

    for method in methods:
        _validate_method(method, event_types)
    for event in events:
        _validate_field_map(event.get("payload"), f"event {event.get('type')} payload")
    for code in payload.get("errors", []):
        if code not in ERROR_CATALOG:
            raise CatalogValidationError(f"unknown error code in catalog: {code}")


def method_names(catalog: dict[str, Any] | None = None) -> set[str]:
    payload = catalog or load_catalog()
    return {item["method"] for item in payload["methods"]}


def event_types(catalog: dict[str, Any] | None = None) -> set[str]:
    payload = catalog or load_catalog()
    return {item["type"] for item in payload["events"]}


def _require_top_level(payload: dict[str, Any]) -> None:
    for key in ("schema_version", "protocol_version", "min_compatible_protocol_version", "methods", "events"):
        if key not in payload:
            raise CatalogValidationError(f"missing top-level catalog field: {key}")


def _validate_method(method: dict[str, Any], event_catalog: set[str]) -> None:
    name = method.get("method")
    if not isinstance(name, str) or not name:
        raise CatalogValidationError("method entry requires method name")
    if not isinstance(method.get("params"), dict):
        raise CatalogValidationError(f"{name} params must be object schema")
    _validate_field_map(method["params"], f"{name} params")
    if not isinstance(method.get("events"), list):
        raise CatalogValidationError(f"{name} events must be list")
    missing_events = [event for event in method["events"] if event not in event_catalog]
    if missing_events:
        raise CatalogValidationError(f"{name} references unknown events: {missing_events}")
    if not method.get("errors"):
        raise CatalogValidationError(f"{name} errors cannot be empty")
    if not method.get("redaction"):
        raise CatalogValidationError(f"{name} redaction cannot be empty")

    long_task = method.get("long_task")
    if not isinstance(long_task, bool):
        raise CatalogValidationError(f"{name} long_task must be boolean")
    if long_task:
        if "accepted" not in method or "result" in method:
            raise CatalogValidationError(f"{name} long task must only declare accepted response")
        _validate_field_map(method["accepted"], f"{name} accepted")
    else:
        if "result" not in method or "accepted" in method:
            raise CatalogValidationError(f"{name} short task must only declare result response")
        _validate_field_map(method["result"], f"{name} result")

    if name.endswith(".stop"):
        if method.get("cancels_request", False):
            raise CatalogValidationError(f"{name} stop method cannot cancel arbitrary request")
        if "request_id" in method["params"]:
            raise CatalogValidationError(f"{name} stop method cannot accept arbitrary request_id")


def _validate_field_map(fields: Any, label: str) -> None:
    if not isinstance(fields, dict) or not fields:
        raise CatalogValidationError(f"{label} must be a non-empty object schema")
    for field_name, spec in fields.items():
        if not isinstance(spec, dict):
            raise CatalogValidationError(f"{label}.{field_name} must be object schema")
        for key in ("type", "required", "redaction"):
            if key not in spec:
                raise CatalogValidationError(f"{label}.{field_name} missing {key}")
        if "nullable" not in spec and "default" not in spec:
            raise CatalogValidationError(f"{label}.{field_name} missing nullable/default")
