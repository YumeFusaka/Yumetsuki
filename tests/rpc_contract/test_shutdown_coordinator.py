from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from python_core.resources.handle_registry import HandleRegistry
from python_core.rpc.shutdown import ShutdownCoordinator
from python_core.rpc.tasks import TaskRegistry


class FakeLogService:
    def __init__(self, order: list[str], fail_flush: bool = False) -> None:
        self.order = order
        self.fail_flush = fail_flush

    def flush(self) -> None:
        self.order.append("flush_logs")
        if self.fail_flush:
            raise RuntimeError("flush failed")


class FakeWorkerService:
    def __init__(self, order: list[str]) -> None:
        self.order = order
        self.stopped = False

    def shutdown(self) -> None:
        self.order.append("stop_plugin_mcp_workers")
        self.stopped = True


def test_shutdown_blocks_new_requests_and_runs_ordered_steps(tmp_path: Path) -> None:
    order: list[str] = []
    task_registry = TaskRegistry()
    handle_registry = HandleRegistry(tmp_path)
    worker_service = FakeWorkerService(order)
    coordinator = ShutdownCoordinator(
        task_registry=task_registry,
        handle_registry=handle_registry,
        log_service=FakeLogService(order),
        plugin_service=worker_service,
        mcp_service=worker_service,
        audit=order,
    )

    coordinator.shutdown(timeout_seconds=1)

    with pytest.raises(RuntimeError, match="sidecar is shutting down"):
        coordinator.ensure_accepting_requests()
    assert order == [
        "block_new_requests",
        "cancel_or_drain_long_tasks",
        "release_handles",
        "flush_logs",
        "stop_plugin_mcp_workers",
        "sidecar.shutdown",
    ]


def test_pending_tasks_enter_one_terminal_state_on_shutdown(tmp_path: Path) -> None:
    task_registry = TaskRegistry()
    for name in ["chat.send", "tts.synthesize", "stt.transcribe", "ocr.capture", "mcp.call_tool", "tools.call"]:
        task_registry.accept_long_task(f"req_{name}", name)
    coordinator = ShutdownCoordinator(task_registry=task_registry, handle_registry=HandleRegistry(tmp_path))

    coordinator.shutdown(timeout_seconds=1)
    coordinator.shutdown(timeout_seconds=1)

    snapshot = task_registry.snapshot()
    assert {item["state"] for item in snapshot} == {"cancelled"}
    assert len(snapshot) == 6


def test_shutdown_releases_handles_and_records_flush_failures(tmp_path: Path) -> None:
    order: list[str] = []
    handle_registry = HandleRegistry(tmp_path)
    handle_id = handle_registry.create_text("req", "data")
    coordinator = ShutdownCoordinator(
        handle_registry=handle_registry,
        log_service=FakeLogService(order, fail_flush=True),
        audit=order,
    )

    coordinator.shutdown(timeout_seconds=1)

    assert handle_registry.release("req", handle_id) is False
    assert any(str(item).find("shutdown.flush_failed") >= 0 for item in coordinator.audit)


def test_shutdown_kills_registered_worker_process_tree(tmp_path: Path) -> None:
    child_pid_file = tmp_path / "child.pid"
    parent_script = (
        "import pathlib, subprocess, sys, time;"
        "child=subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)']);"
        "pathlib.Path(sys.argv[1]).write_text(str(child.pid), encoding='utf-8');"
        "time.sleep(30)"
    )
    parent = subprocess.Popen([sys.executable, "-c", parent_script, str(child_pid_file)])
    deadline = time.time() + 5
    while not child_pid_file.exists() and time.time() < deadline:
        time.sleep(0.05)
    assert child_pid_file.exists()
    child_pid = int(child_pid_file.read_text(encoding="utf-8"))

    coordinator = ShutdownCoordinator()
    coordinator.register_process(parent, include_children=True)
    coordinator.shutdown(timeout_seconds=2)

    assert parent.poll() is not None
    assert not _pid_is_alive(child_pid)


def _pid_is_alive(pid: int) -> bool:
    if os.name == "nt":
        result = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
            capture_output=True,
            text=True,
            check=False,
        )
        return str(pid) in result.stdout
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True
