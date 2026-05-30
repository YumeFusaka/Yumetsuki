from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import time
from typing import Any

from .errors import make_error
from .protocol import build_hello_result
from .schema.schema_hash import load_catalog
from .tasks import TaskRegistry


Handler = Callable[[dict[str, Any], "RegistryContext | None"], dict[str, Any]]


@dataclass
class RegistryContext:
    started_at: float
    task_registry: TaskRegistry
    runtime_paths_ready: bool = False
    shutdown_coordinator: Any | None = None


def _ok(result: dict[str, Any]) -> dict[str, Any]:
    return {"ok": True, "result": result}


def _error(code: str, details: dict[str, Any] | None = None, message: str | None = None) -> dict[str, Any]:
    return {
        "ok": False,
        "error": make_error(code, message=message, details=details).to_dict(),
    }


def _not_ready_handler(_: dict[str, Any], __: RegistryContext | None = None) -> dict[str, Any]:
    return _error("sidecar.not_ready", {"stage": "phase1.catalog_stub"}, "handler is not implemented yet")


def _hello_handler(params: dict[str, Any], context: RegistryContext | None = None) -> dict[str, Any]:
    versions = params.get("supported_versions", [1])
    if not isinstance(versions, list) or not all(isinstance(item, int) for item in versions):
        return _error("rpc.invalid_params", {"field": "supported_versions"})
    return _ok(build_hello_result(versions, bool(context and context.runtime_paths_ready)))


def _health_handler(_: dict[str, Any], context: RegistryContext | None = None) -> dict[str, Any]:
    uptime_ms = int((time.monotonic() - (context.started_at if context else time.monotonic())) * 1000)
    return _ok({"healthy": True, "status": "ok", "uptime_ms": max(0, uptime_ms)})


def _shutdown_handler(_: dict[str, Any], context: RegistryContext | None = None) -> dict[str, Any]:
    if context and context.shutdown_coordinator:
        context.shutdown_coordinator.shutdown()
    return _ok({"accepted": True, "accepted_shutdown": True})


def _cancel_handler(params: dict[str, Any], context: RegistryContext | None = None) -> dict[str, Any]:
    target_request_id = params.get("target_request_id")
    if not isinstance(target_request_id, str):
        return _error("rpc.invalid_params", {"field": "target_request_id"})
    try:
        if context is None:
            raise KeyError("sidecar.task_not_found")
        result = context.task_registry.cancel(target_request_id)
    except KeyError:
        return _error("sidecar.task_not_found", {"target_request_id": target_request_id})
    result["target_request_id"] = target_request_id
    return _ok(result)


def _task_snapshot_handler(_: dict[str, Any], context: RegistryContext | None = None) -> dict[str, Any]:
    return _ok({"tasks": context.task_registry.snapshot() if context else []})


def registered_methods() -> set[str]:
    return {method["method"] for method in load_catalog().get("methods", [])}


REGISTRY: dict[str, Handler] = {name: _not_ready_handler for name in registered_methods()}
REGISTRY.update(
    {
        "sidecar.hello": _hello_handler,
        "sidecar.health": _health_handler,
        "sidecar.shutdown": _shutdown_handler,
        "sidecar.cancel": _cancel_handler,
        "sidecar.task_snapshot": _task_snapshot_handler,
    }
)
CATALOG_BY_METHOD = {method["method"]: method for method in load_catalog().get("methods", [])}


def get_handler(method: str) -> Handler | None:
    return REGISTRY.get(method)


def dispatch_method(method: str, params: dict[str, Any], context: RegistryContext | None = None) -> dict[str, Any]:
    handler = get_handler(method)
    if handler is None:
        return _error("rpc.method_not_found", {"method": method})
    try:
        _validate_params(method, params)
    except (TypeError, ValueError) as exc:
        return _error("rpc.invalid_params", {"method": method, "reason": str(exc)})
    return handler(params, context)


def _validate_params(method: str, params: dict[str, Any]) -> None:
    if not isinstance(params, dict):
        raise TypeError("params must be object")
    schema = CATALOG_BY_METHOD[method].get("params", {})
    for name, spec in schema.items():
        if spec.get("required") is True and name not in params:
            raise ValueError(f"missing required param: {name}")
        if name not in params:
            continue
        value = params[name]
        if value is None:
            if spec.get("nullable") is True:
                continue
            raise TypeError(f"{name} must not be null")
        _assert_param_type(name, value, spec)


def _assert_param_type(name: str, value: Any, spec: dict[str, Any]) -> None:
    expected = spec["type"]
    if expected == "string" and not isinstance(value, str):
        raise TypeError(f"{name} must be string")
    if expected == "handle" and not isinstance(value, str):
        raise TypeError(f"{name} must be handle")
    if expected == "integer" and (not isinstance(value, int) or isinstance(value, bool)):
        raise TypeError(f"{name} must be integer")
    if expected == "boolean" and not isinstance(value, bool):
        raise TypeError(f"{name} must be boolean")
    if expected == "array" and not isinstance(value, list):
        raise TypeError(f"{name} must be array")
    if expected == "object" and not isinstance(value, dict):
        raise TypeError(f"{name} must be object")
    if expected == "literal" and value != spec.get("value"):
        raise TypeError(f"{name} must be literal {spec.get('value')}")
