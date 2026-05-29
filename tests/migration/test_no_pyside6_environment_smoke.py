from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _venv_python(venv: Path) -> Path:
    candidate = venv / "Scripts" / "python.exe"
    if candidate.exists():
        return candidate
    return venv / "bin" / "python"


def _run(args: list[str | Path], **kwargs) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    return subprocess.run(
        [str(arg) for arg in args],
        cwd=ROOT,
        env=env,
        capture_output=True,
        check=False,
        **kwargs,
    )


def test_sidecar_runs_in_isolated_environment_without_pyside6(tmp_path: Path) -> None:
    venv = tmp_path / "venv"
    created = _run([sys.executable, "-m", "venv", venv], text=True, encoding="utf-8", errors="replace")
    assert created.returncode == 0, created.stdout + created.stderr
    python = _venv_python(venv)

    installed = _run(
        [python, "-m", "pip", "install", "--disable-pip-version-check", "-r", ROOT / "requirements-sidecar.txt"],
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    assert installed.returncode == 0, installed.stdout + installed.stderr

    pyside_check = _run(
        [
            python,
            "-c",
            "import importlib.util, sys; sys.exit(0 if importlib.util.find_spec('PySide6') is None else 1)",
        ],
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    assert pyside_check.returncode == 0, "隔离 venv 不应能导入 PySide6"

    request = {
        "kind": "request",
        "request_id": "req_no_pyside6_smoke",
        "method": "sidecar.hello",
        "params": {"supported_protocol_versions": [1]},
        "protocol_version": 1,
        "trace_id": "trace_no_pyside6_smoke",
        "parent_trace_id": None,
        "session_id": "sess_no_pyside6_smoke",
        "deadline_ms": 30000,
    }
    payload = json.dumps(request, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8") + b"\n"
    completed = _run([python, "-m", "python_core.sidecar_main", "--stdio"], input=payload)

    assert completed.returncode == 0, completed.stderr.decode("utf-8", errors="replace")
    stdout_lines = [line for line in completed.stdout.splitlines() if line.strip()]
    assert stdout_lines, "sidecar stdout 必须至少输出一个协议帧"
    frames = [json.loads(line.decode("utf-8")) for line in stdout_lines]
    assert all(frame["kind"] in {"response", "event"} for frame in frames)
    response = next(frame for frame in frames if frame["kind"] == "response")
    assert response["ok"] is True
    assert response["result"]["selected_protocol_version"] == 1
