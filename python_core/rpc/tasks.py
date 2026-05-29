from __future__ import annotations

from dataclasses import dataclass, field
import threading
import time
from typing import Any, Literal

from .context import RpcContext
from .errors import RpcError, make_error
from .event_publisher import RpcEventPublisher


TaskState = Literal["created", "running", "accepted", "streaming", "cancelling", "done", "error", "cancelled"]


class TaskStateError(RuntimeError):
    def __init__(self, rpc_error: RpcError):
        super().__init__(rpc_error.message)
        self.rpc_error = rpc_error


class CancelToken:
    def __init__(self) -> None:
        self._event = threading.Event()
        self.reason: str | None = None

    def cancel(self, reason: str | None = None) -> None:
        self.reason = reason
        self._event.set()

    @property
    def cancelled(self) -> bool:
        return self._event.is_set()

    def throw_if_cancelled(self) -> None:
        if self.cancelled:
            raise TaskStateError(make_error("chat.cancelled", details={"reason": self.reason or "cancelled"}))


@dataclass
class TaskHandle:
    request_id: str
    task_type: str
    state: TaskState
    created_at_ms: int
    deadline_ms: int | None
    owner: str
    sidecar_generation: int
    trace_id: str = ""
    parent_trace_id: str | None = None
    session_id: str = ""
    cancel_token: CancelToken = field(default_factory=CancelToken)
    last_sequence: int = 0
    terminal_summary: dict[str, Any] | None = None
    terminal_error: RpcError | None = None

    @property
    def terminal(self) -> bool:
        return self.state in ("done", "error", "cancelled")


class TaskRegistry:
    def __init__(self, event_publisher: RpcEventPublisher | None = None, sidecar_generation: int = 1) -> None:
        self._tasks: dict[str, TaskHandle] = {}
        self._lock = threading.RLock()
        self._event_publisher = event_publisher or RpcEventPublisher()
        self.sidecar_generation = sidecar_generation

    @property
    def event_publisher(self) -> RpcEventPublisher:
        return self._event_publisher

    def accept_long_task(
        self,
        request_id: str,
        task_type: str,
        deadline_ms: int | None = None,
        owner: str = "sidecar",
        context: RpcContext | None = None,
    ) -> dict[str, Any]:
        with self._lock:
            if request_id in self._tasks and not self._tasks[request_id].terminal:
                raise TaskStateError(make_error("rpc.invalid_params", details={"request_id": request_id}))
            self._tasks[request_id] = TaskHandle(
                request_id=request_id,
                task_type=task_type,
                state="accepted",
                created_at_ms=_now_ms(),
                deadline_ms=deadline_ms,
                owner=owner,
                sidecar_generation=self.sidecar_generation,
                trace_id=context.trace_id if context is not None else "",
                parent_trace_id=context.parent_trace_id if context is not None else None,
                session_id=context.session_id if context is not None else "",
            )
            return {
                "status": "accepted",
                "request_id": request_id,
                "task_type": task_type,
                "sidecar_generation": self.sidecar_generation,
                "started_at_ms": self._tasks[request_id].created_at_ms,
            }

    def mark_streaming(self, request_id: str) -> None:
        with self._lock:
            task = self._require_task(request_id)
            if task.terminal:
                return
            task.state = "streaming"

    def publish_terminal_event(
        self,
        context: RpcContext,
        event_type: str,
        terminal_state: Literal["done", "error", "cancelled"],
        summary: dict[str, Any] | None = None,
        error: RpcError | None = None,
    ) -> dict[str, Any]:
        with self._lock:
            task = self._require_task(context.request_id)
            if task.terminal:
                raise TaskStateError(make_error("rpc.duplicate_terminal", details={"request_id": context.request_id}))
            task.state = terminal_state
            task.terminal_summary = summary or {}
            task.terminal_error = error
            payload: dict[str, Any] = {
                "terminal_state": terminal_state,
                "summary": task.terminal_summary,
            }
            if terminal_state == "error" and error is not None:
                payload["error"] = error.to_dict()
            event = self._event_publisher.publish(event_type, context, payload)
            task.last_sequence = event["sequence"]
            return event

    def cancel(self, request_id: str, reason: str | None = None) -> dict[str, Any]:
        with self._lock:
            task = self._tasks.get(request_id)
            if task is None:
                return {"status": "not_found", "terminal_state": None}
            if task.terminal:
                return {
                    "status": "already_terminal",
                    "terminal_state": task.state,
                    "summary": task.terminal_summary or {},
                }
            task.cancel_token.cancel(reason)
            context = RpcContext(
                request_id=task.request_id,
                trace_id=task.trace_id or f"trace_{task.request_id}",
                parent_trace_id=task.parent_trace_id,
                session_id=task.session_id,
                deadline_ms=task.deadline_ms,
            )
            event = self.publish_terminal_event(
                context,
                _cancelled_event_type(task.task_type),
                "cancelled",
                summary={"reason": reason or "cancelled", "task_type": task.task_type},
            )
            return {
                "status": "cancelled",
                "terminal_state": "cancelled",
                "summary": task.terminal_summary or {},
                "last_sequence": event["sequence"],
            }

    def snapshot(self, request_id: str) -> dict[str, Any] | None:
        with self._lock:
            task = self._tasks.get(request_id)
            if task is None:
                return None
            return {
                "request_id": task.request_id,
                "task_type": task.task_type,
                "task_state": task.state,
                "last_sequence": task.last_sequence,
                "terminal_summary": task.terminal_summary,
                "sidecar_generation": task.sidecar_generation,
            }

    def active_count(self) -> int:
        with self._lock:
            return sum(1 for task in self._tasks.values() if not task.terminal)

    def mark_pending_restarted(self) -> int:
        with self._lock:
            count = 0
            for task in self._tasks.values():
                if task.terminal:
                    continue
                task.state = "error"
                task.terminal_error = make_error("sidecar.restarted")
                task.terminal_summary = {"reason": "sidecar.restarted"}
                count += 1
            return count

    def _require_task(self, request_id: str) -> TaskHandle:
        task = self._tasks.get(request_id)
        if task is None:
            raise TaskStateError(make_error("sidecar.task_not_found", details={"request_id": request_id}))
        return task


def _now_ms() -> int:
    return int(time.time() * 1000)


def _cancelled_event_type(task_type: str) -> str:
    if task_type.startswith("character."):
        return "character.assets_cancelled"
    if task_type.startswith("chat."):
        return "chat.cancelled"
    if task_type.startswith("tts."):
        return "tts.cancelled"
    if task_type.startswith("stt."):
        return "stt.cancelled"
    if task_type.startswith("ocr."):
        return "ocr.cancelled"
    if task_type.startswith("logs."):
        return "log.cancelled"
    if task_type.startswith("tools."):
        return "tool.cancelled"
    if task_type.startswith("diagnostics."):
        return "diagnostic.cancelled"
    if task_type.startswith("plugins."):
        return "plugin.cancelled"
    if task_type.startswith("mcp."):
        return "mcp.cancelled"
    return "sidecar.cancelled"
