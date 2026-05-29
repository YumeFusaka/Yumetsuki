from __future__ import annotations

from dataclasses import dataclass, field

from .tasks import TaskRegistry


@dataclass
class ShutdownCoordinator:
    task_registry: TaskRegistry
    steps: list[str] = field(default_factory=list)
    blocked_new_requests: bool = False

    def shutdown(self) -> dict[str, object]:
        self.blocked_new_requests = True
        self.steps.extend(
            [
                "block_new_requests",
                "cancel_or_drain_long_tasks",
                "release_handles",
                "flush_logs",
                "stop_plugin_mcp_workers",
                "sidecar.shutdown",
            ]
        )
        self.task_registry.mark_pending_restarted()
        return {"accepted_shutdown": True, "steps": list(self.steps)}
