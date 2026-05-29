from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Any, Callable

from python_core import __version__
from python_core.runtime_paths import RuntimePaths

from .context import RpcContext
from .envelope import RequestEnvelope, response_payload
from .errors import RpcError, make_error
from .schema.schema_hash import compute_schema_hash, load_catalog
from .schema.validate import method_names, validate_catalog
from .services import ServiceError, build_service_handlers
from .shutdown import ShutdownCoordinator
from .tasks import TaskRegistry, TaskStateError


class RpcHandlerError(Exception):
    def __init__(self, rpc_error: RpcError):
        super().__init__(rpc_error.message)
        self.rpc_error = rpc_error


Handler = Callable[[RequestEnvelope, "SidecarRuntime"], dict[str, Any]]


@dataclass
class SidecarRuntime:
    runtime_paths: RuntimePaths
    task_registry: TaskRegistry
    start_time_ms: int
    shutdown_requested: bool = False
    sidecar_generation: int = 1

    @classmethod
    def create(cls, runtime_paths: RuntimePaths) -> "SidecarRuntime":
        task_registry = TaskRegistry(sidecar_generation=1)
        return cls(runtime_paths=runtime_paths, task_registry=task_registry, start_time_ms=_now_ms())

    @property
    def uptime_ms(self) -> int:
        return max(0, _now_ms() - self.start_time_ms)


class MethodRegistry:
    def __init__(self, catalog: dict[str, Any] | None = None) -> None:
        self.catalog = catalog or load_catalog()
        validate_catalog(self.catalog)
        self._handlers: dict[str, Handler] = {}
        for name in method_names(self.catalog):
            self._handlers[name] = self._stub_handler(name)
        self._handlers.update(
            {
                "sidecar.hello": _handle_sidecar_hello,
                "sidecar.health": _handle_sidecar_health,
                "sidecar.shutdown": _handle_sidecar_shutdown,
                "sidecar.cancel": _handle_sidecar_cancel,
                "sidecar.task_snapshot": _handle_sidecar_task_snapshot,
            }
        )
        self._handlers.update(build_service_handlers())

    @property
    def registered_methods(self) -> set[str]:
        return set(self._handlers)

    @property
    def catalog_methods(self) -> set[str]:
        return method_names(self.catalog)

    def dispatch(self, request: RequestEnvelope, runtime: SidecarRuntime) -> dict[str, Any]:
        handler = self._handlers.get(request.method)
        if handler is None:
            return response_payload(
                request,
                error=make_error("rpc.method_not_found", details={"method": request.method}),
            )
        if request.protocol_version != int(self.catalog["protocol_version"]):
            return response_payload(
                request,
                error=make_error(
                    "rpc.protocol_unsupported",
                    details={
                        "requested_protocol_version": request.protocol_version,
                        "sidecar_protocol_versions": [self.catalog["protocol_version"]],
                    },
                ),
            )
        if runtime.shutdown_requested and request.method not in {
            "sidecar.health",
            "sidecar.task_snapshot",
            "sidecar.shutdown",
        }:
            return response_payload(
                request,
                error=make_error("sidecar.not_ready", details={"state": "shutting_down", "method": request.method}),
            )
        try:
            result = handler(request, runtime)
        except TaskStateError as exc:
            return response_payload(request, error=exc.rpc_error)
        except RpcHandlerError as exc:
            return response_payload(request, error=exc.rpc_error)
        except ServiceError as exc:
            return response_payload(request, error=exc.rpc_error)
        except (TypeError, ValueError) as exc:
            return response_payload(
                request,
                error=make_error("rpc.invalid_params", details={"method": request.method, "summary": str(exc)}),
            )
        return response_payload(request, result=result)

    def _stub_handler(self, method: str) -> Handler:
        def handler(request: RequestEnvelope, runtime: SidecarRuntime) -> dict[str, Any]:
            raise RpcHandlerError(
                make_error(
                    "sidecar.not_ready",
                    details={"method": method},
                )
            )

        return handler


def build_default_registry() -> MethodRegistry:
    return MethodRegistry()


def _handle_sidecar_hello(request: RequestEnvelope, runtime: SidecarRuntime) -> dict[str, Any]:
    supported = request.params.get("supported_protocol_versions") or [request.protocol_version]
    if not isinstance(supported, list) or not all(isinstance(item, int) for item in supported):
        raise RpcHandlerError(make_error("rpc.invalid_params", details={"field": "supported_protocol_versions"}))
    compatible = sorted({version for version in supported if version == 1})
    if not compatible:
        raise RpcHandlerError(
            make_error(
                "rpc.protocol_unsupported",
                details={"supported_protocol_versions": supported, "sidecar_protocol_versions": [1]},
            )
        )
    return {
        "selected_protocol_version": compatible[-1],
        "min_compatible_protocol_version": 1,
        "sidecar_version": __version__,
        "capabilities": sorted(method_names()),
        "runtime_paths_ready": runtime.runtime_paths.ready,
        "schema_hash": compute_schema_hash(),
    }


def _handle_sidecar_health(request: RequestEnvelope, runtime: SidecarRuntime) -> dict[str, Any]:
    result: dict[str, Any] = {
        "status": "healthy" if not runtime.shutdown_requested else "shutting_down",
        "active_task_count": runtime.task_registry.active_count(),
        "uptime_ms": runtime.uptime_ms,
    }
    if request.params.get("include_tasks"):
        result["tasks"] = []
    return result


def _handle_sidecar_shutdown(request: RequestEnvelope, runtime: SidecarRuntime) -> dict[str, Any]:
    runtime.shutdown_requested = True
    coordinator = ShutdownCoordinator(runtime.task_registry)
    result = coordinator.shutdown()
    context = RpcContext(
        request_id=request.request_id,
        trace_id=request.trace_id,
        parent_trace_id=request.parent_trace_id,
        session_id=request.session_id,
        deadline_ms=request.deadline_ms,
    )
    runtime.task_registry.event_publisher.publish("sidecar.exiting", context, {"state": "shutting_down"})
    return result


def _handle_sidecar_cancel(request: RequestEnvelope, runtime: SidecarRuntime) -> dict[str, Any]:
    target_request_id = request.params.get("request_id")
    if not isinstance(target_request_id, str) or not target_request_id:
        raise RpcHandlerError(make_error("rpc.invalid_params", details={"field": "request_id"}))
    result = runtime.task_registry.cancel(target_request_id, request.params.get("reason"))
    if result["status"] == "not_found":
        raise RpcHandlerError(make_error("sidecar.task_not_found", details={"request_id": target_request_id}))
    return result


def _handle_sidecar_task_snapshot(request: RequestEnvelope, runtime: SidecarRuntime) -> dict[str, Any]:
    target_request_id = request.params.get("request_id")
    if not isinstance(target_request_id, str) or not target_request_id:
        raise RpcHandlerError(make_error("rpc.invalid_params", details={"field": "request_id"}))
    snapshot = runtime.task_registry.snapshot(target_request_id)
    if snapshot is None:
        raise RpcHandlerError(make_error("sidecar.task_not_found", details={"request_id": target_request_id}))
    return {
        "task_state": snapshot["task_state"],
        "last_sequence": snapshot["last_sequence"],
        "terminal_summary": snapshot["terminal_summary"],
    }




def _now_ms() -> int:
    return int(time.time() * 1000)
