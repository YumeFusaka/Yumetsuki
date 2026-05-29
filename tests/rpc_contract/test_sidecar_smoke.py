from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from python_core.rpc.framing import decode_frame, encode_frame


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def request(method: str, request_id: str, params: dict[str, object] | None = None) -> dict[str, object]:
    return {
        "kind": "request",
        "request_id": request_id,
        "method": method,
        "params": params or {},
        "protocol_version": 1,
        "trace_id": f"trace_{request_id}",
        "parent_trace_id": None,
        "session_id": "sess_smoke",
        "deadline_ms": 30000,
    }


def run_sidecar(requests: list[dict[str, object]]) -> tuple[list[dict[str, object]], str]:
    payload = b"".join(encode_frame(item) for item in requests)
    completed = subprocess.run(
        [sys.executable, "-m", "python_core.sidecar_main", "--stdio"],
        cwd=PROJECT_ROOT,
        input=payload,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr.decode("utf-8", errors="replace")
    frames = [decode_frame(line) for line in completed.stdout.splitlines(keepends=True)]
    return frames, completed.stderr.decode("utf-8", errors="replace")


def test_sidecar_hello_health_cancel_shutdown_smoke() -> None:
    frames, stderr = run_sidecar(
        [
            request("sidecar.hello", "req_hello", {"supported_protocol_versions": [1]}),
            request("sidecar.health", "req_health", {"include_tasks": True}),
            request("sidecar.cancel", "req_cancel", {"request_id": "missing"}),
            request("sidecar.shutdown", "req_shutdown", {"reason": "test"}),
        ]
    )
    responses = {frame["request_id"]: frame for frame in frames if frame["kind"] == "response"}
    assert responses["req_hello"]["ok"] is True
    assert responses["req_hello"]["result"]["selected_protocol_version"] == 1
    assert responses["req_hello"]["result"]["schema_hash"]
    assert responses["req_health"]["result"]["status"] == "healthy"
    assert responses["req_cancel"]["ok"] is False
    assert responses["req_cancel"]["error"]["code"] == "sidecar.task_not_found"
    assert responses["req_shutdown"]["result"]["accepted_shutdown"] is True
    assert "QApplication" not in stderr
