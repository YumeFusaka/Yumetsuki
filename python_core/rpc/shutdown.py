from __future__ import annotations

import os
import subprocess
import time
from typing import Any

from .tasks import TERMINAL_STATES, TaskRegistry


class ShutdownCoordinator:
    def __init__(
        self,
        task_registry: TaskRegistry | None = None,
        handle_registry: Any | None = None,
        log_service: Any | None = None,
        plugin_service: Any | None = None,
        mcp_service: Any | None = None,
        audit: list[Any] | None = None,
    ) -> None:
        self.task_registry = task_registry or TaskRegistry()
        self.handle_registry = handle_registry
        self.log_service = log_service
        self.plugin_service = plugin_service
        self.mcp_service = mcp_service
        self.audit: list[Any] = audit if audit is not None else []
        self._record_steps = audit is not None
        self._processes: list[tuple[subprocess.Popen, bool]] = []
        self._shutting_down = False

    def register_process(self, process: subprocess.Popen, include_children: bool = False) -> None:
        self._processes.append((process, include_children))

    def ensure_accepting_requests(self) -> None:
        if self._shutting_down:
            raise RuntimeError("sidecar is shutting down")

    def shutdown(self, timeout_seconds: float = 1.0) -> None:
        self._block_new_requests()
        self._cancel_or_drain_long_tasks()
        self._release_handles()
        self._flush_logs()
        self._stop_plugin_mcp_workers(timeout_seconds)
        self._record_step("sidecar.shutdown")

    def mark_restarted(self) -> list[dict[str, Any]]:
        return self.task_registry.mark_pending_restarted()

    def _block_new_requests(self) -> None:
        self._shutting_down = True
        self._record_step("block_new_requests")

    def _cancel_or_drain_long_tasks(self) -> None:
        self._record_step("cancel_or_drain_long_tasks")
        for item in self.task_registry.snapshot():
            if item["state"] in {state.value for state in TERMINAL_STATES}:
                continue
            request_id = item["request_id"]
            try:
                self.task_registry.cancel(request_id)
                self.task_registry.publish_terminal_event(request_id, "cancelled", "sidecar shutdown")
            except ValueError as exc:
                if str(exc) != "rpc.duplicate_terminal":
                    self.audit.append({"event": "shutdown.task_terminal_failed", "request_id": request_id, "error": str(exc)})
            except KeyError:
                continue

    def _release_handles(self) -> None:
        self._record_step("release_handles")
        if self.handle_registry is not None:
            self.handle_registry.shutdown()

    def _flush_logs(self) -> None:
        if self.log_service is None:
            self._record_step("flush_logs")
            return
        try:
            self.log_service.flush()
        except Exception as exc:  # noqa: BLE001
            self.audit.append({"event": "shutdown.flush_failed", "error": str(exc)})
        self._record_step("flush_logs")

    def _stop_plugin_mcp_workers(self, timeout_seconds: float) -> None:
        seen: set[int] = set()
        for service in (self.plugin_service, self.mcp_service):
            if service is None or id(service) in seen:
                continue
            seen.add(id(service))
            service.shutdown()
        self._record_step("stop_plugin_mcp_workers")
        self._shutdown_registered_processes(timeout_seconds)

    def _shutdown_registered_processes(self, timeout_seconds: float) -> None:
        deadline = time.time() + timeout_seconds
        for process, include_children in self._processes:
            if include_children:
                self._kill_process_tree(process)
                continue
            if process.poll() is None:
                process.terminate()
        for process, include_children in self._processes:
            if include_children:
                try:
                    process.wait(timeout=max(0.0, deadline - time.time()))
                except subprocess.TimeoutExpired:
                    self.audit.append({"event": "shutdown.timeout", "pid": process.pid})
                    self._kill_process_tree(process)
                    process.wait(timeout=1)
                continue
            remaining = max(0.0, deadline - time.time())
            try:
                process.wait(timeout=remaining)
            except subprocess.TimeoutExpired:
                self.audit.append({"event": "shutdown.timeout", "pid": process.pid})
                process.kill()
                process.wait(timeout=1)

    def _kill_process_tree(self, process: subprocess.Popen) -> None:
        if process.poll() is not None:
            return
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
        else:
            process.kill()

    def _record_step(self, event: str) -> None:
        if not self._record_steps:
            return
        if event in self.audit:
            return
        self.audit.append(event)
