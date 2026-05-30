from __future__ import annotations

import subprocess
import sys

from python_core.rpc.shutdown import ShutdownCoordinator


def test_shutdown_terminates_registered_worker_process() -> None:
    process = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    coordinator = ShutdownCoordinator()
    coordinator.register_process(process)
    coordinator.shutdown(timeout_seconds=2)
    assert process.poll() is not None


def test_shutdown_timeout_writes_audit_summary() -> None:
    class FakeProcess:
        pid = 12345

        def __init__(self) -> None:
            self.killed = False

        def poll(self):
            return None if not self.killed else -9

        def terminate(self) -> None:
            return None

        def wait(self, timeout=None):
            if not self.killed:
                raise subprocess.TimeoutExpired("fake", timeout)
            return -9

        def kill(self) -> None:
            self.killed = True

    process = FakeProcess()
    coordinator = ShutdownCoordinator()
    coordinator.register_process(process)
    coordinator.shutdown(timeout_seconds=0.01)
    assert process.poll() is not None
    assert coordinator.audit[0]["event"] == "shutdown.timeout"
