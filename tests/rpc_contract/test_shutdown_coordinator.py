from __future__ import annotations

from python_core.rpc.shutdown import ShutdownCoordinator
from python_core.rpc.tasks import TaskRegistry


def test_shutdown_coordinator_marks_pending_tasks_restarted_and_orders_steps() -> None:
    registry = TaskRegistry()
    registry.accept_long_task("req_shutdown_task", "chat.send")
    coordinator = ShutdownCoordinator(registry)

    result = coordinator.shutdown()

    assert result["accepted_shutdown"] is True
    assert result["steps"][:3] == ["block_new_requests", "cancel_or_drain_long_tasks", "release_handles"]
    assert registry.snapshot("req_shutdown_task")["task_state"] == "error"
    assert coordinator.blocked_new_requests is True
