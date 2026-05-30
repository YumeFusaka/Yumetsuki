from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from threading import Lock
from typing import Any

from .errors import make_error


class TaskState(str, Enum):
    CREATED = "created"
    RUNNING = "running"
    ACCEPTED = "accepted"
    STREAMING = "streaming"
    CANCELLING = "cancelling"
    DONE = "done"
    ERROR = "error"
    CANCELLED = "cancelled"


TERMINAL_STATES = {TaskState.DONE, TaskState.ERROR, TaskState.CANCELLED}


@dataclass
class TaskHandle:
    request_id: str
    task_type: str
    state: TaskState
    created_at: float
    deadline: float | None
    owner: str
    sidecar_generation: int
    next_sequence: int = 1
    terminal_summary: dict[str, Any] | None = None
    cancel_requested: bool = False
    lock: Lock = field(default_factory=Lock, repr=False)


class TaskRegistry:
    def __init__(self, sidecar_generation: int = 1) -> None:
        self.sidecar_generation = sidecar_generation
        self._tasks: dict[str, TaskHandle] = {}
        self._lock = Lock()

    def create_short_task(self, request_id: str, task_type: str, owner: str = "sidecar", deadline: float | None = None) -> TaskHandle:
        handle = TaskHandle(request_id, task_type, TaskState.CREATED, time.time(), deadline, owner, self.sidecar_generation)
        with self._lock:
            self._tasks[request_id] = handle
        return handle

    def accept_long_task(self, request_id: str, task_type: str, owner: str = "sidecar", deadline: float | None = None) -> dict[str, Any]:
        handle = TaskHandle(request_id, task_type, TaskState.ACCEPTED, time.time(), deadline, owner, self.sidecar_generation)
        with self._lock:
            self._tasks[request_id] = handle
        return {
            "status": "accepted",
            "request_id": request_id,
            "task_type": task_type,
            "sidecar_generation": self.sidecar_generation,
        }

    def mark_running(self, request_id: str) -> None:
        self._set_state(request_id, TaskState.RUNNING, {TaskState.CREATED})

    def mark_streaming(self, request_id: str) -> None:
        self._set_state(request_id, TaskState.STREAMING, {TaskState.ACCEPTED, TaskState.STREAMING})

    def complete_short_task(self, request_id: str, ok: bool) -> bool:
        handle = self._get(request_id)
        with handle.lock:
            if handle.deadline is not None and time.time() > handle.deadline:
                return False
            if handle.state in TERMINAL_STATES:
                return False
            handle.state = TaskState.DONE if ok else TaskState.ERROR
            handle.terminal_summary = {"state": handle.state.value}
            return True

    def publish_terminal_event(
        self,
        request_id: str,
        state: str,
        summary: str,
        error: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if state not in {"done", "error", "cancelled"}:
            raise ValueError("invalid terminal state")
        handle = self._get(request_id)
        with handle.lock:
            if handle.state in TERMINAL_STATES:
                raise ValueError("rpc.duplicate_terminal")
            handle.state = TaskState(state)
            sequence = handle.next_sequence
            handle.next_sequence += 1
            payload = {"state": state, "summary": summary, "error": error}
            if state == "error" and error is None:
                payload["error"] = make_error("rpc.invalid_params", details={"stage": "terminal"}).to_dict()
            handle.terminal_summary = payload
        return {
            "kind": "event",
            "type": f"{handle.task_type}.{state}",
            "request_id": request_id,
            "sequence": sequence,
            "payload": payload,
        }

    def cancel(self, request_id: str) -> dict[str, Any]:
        handle = self._get(request_id)
        with handle.lock:
            if handle.state in TERMINAL_STATES:
                return {"state": handle.state.value, "request_id": request_id, "terminal": handle.terminal_summary}
            handle.cancel_requested = True
            handle.state = TaskState.CANCELLING
            return {"state": "cancelling", "request_id": request_id}

    def mark_pending_restarted(self) -> list[dict[str, Any]]:
        events = []
        with self._lock:
            handles = list(self._tasks.values())
        for handle in handles:
            with handle.lock:
                if handle.state in TERMINAL_STATES:
                    continue
            events.append(
                self.publish_terminal_event(
                    handle.request_id,
                    "error",
                    "sidecar restarted",
                    make_error("sidecar.restarted", details={"generation": self.sidecar_generation}).to_dict(),
                )
            )
        return events

    def next_sequence(self, request_id: str) -> int:
        handle = self._get(request_id)
        with handle.lock:
            sequence = handle.next_sequence
            handle.next_sequence += 1
            return sequence

    def snapshot(self) -> list[dict[str, Any]]:
        with self._lock:
            handles = list(self._tasks.values())
        return [
            {
                "request_id": handle.request_id,
                "task_type": handle.task_type,
                "state": handle.state.value,
                "sidecar_generation": handle.sidecar_generation,
            }
            for handle in handles
        ]

    def _set_state(self, request_id: str, state: TaskState, allowed: set[TaskState]) -> None:
        handle = self._get(request_id)
        with handle.lock:
            if handle.state not in allowed:
                raise ValueError(f"invalid transition {handle.state.value}->{state.value}")
            handle.state = state

    def _get(self, request_id: str) -> TaskHandle:
        with self._lock:
            handle = self._tasks.get(request_id)
        if handle is None:
            raise KeyError("sidecar.task_not_found")
        return handle
