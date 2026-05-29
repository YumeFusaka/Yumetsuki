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
        "session_id": "sess_stdout",
        "deadline_ms": 30000,
    }


def test_sidecar_stdout_contains_only_protocol_frames() -> None:
    payload = b"".join(
        encode_frame(item)
        for item in [
            request("sidecar.hello", "req_hello", {"supported_protocol_versions": [1]}),
            request("config.get_all", "req_config"),
            request("logs.query", "req_logs"),
            request("chat.send", "req_chat", {"text": "hello", "session_id": "sess_stdout"}),
            request("sidecar.shutdown", "req_shutdown"),
        ]
    )
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
    assert frames
    assert all(frame["kind"] in {"response", "event"} for frame in frames)
    assert any(frame["kind"] == "event" and frame["type"] == "chat.done" for frame in frames)


def test_static_stdout_scan_passes() -> None:
    completed = subprocess.run(
        [sys.executable, "scripts/check_no_stdout_in_sidecar.py"],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
