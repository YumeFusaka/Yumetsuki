from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from python_core.rpc.framing import decode_frame, encode_frame
from python_core.rpc.schema.schema_hash import SCHEMA_HASH


ROOT = Path(__file__).resolve().parents[2]


def request(method: str, params: dict[str, Any] | None = None, request_id: str | None = None) -> dict[str, Any]:
    return {
        "kind": "request",
        "protocol_version": 1,
        "request_id": request_id or method.replace(".", "_"),
        "trace_id": f"trace_{request_id or method}",
        "parent_trace_id": None,
        "session_id": "session",
        "method": method,
        "params": params or {},
        "deadline_ms": 30000,
    }


def run_sidecar(
    requests: list[dict[str, Any]],
    runtime_paths: dict[str, Any] | None = None,
    env: dict[str, str] | None = None,
) -> tuple[list[dict[str, Any]], str]:
    merged_env = os.environ.copy()
    merged_env.update(env or {})
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "python_core.sidecar_main",
            "--stdio",
            "--runtime-paths-json",
            json.dumps(runtime_paths or {}),
        ],
        cwd=ROOT,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=merged_env,
    )
    assert process.stdin is not None
    payload = b"".join(encode_frame(item) for item in requests)
    stdout, stderr = process.communicate(payload, timeout=10)
    assert process.returncode == 0, stderr.decode("utf-8", errors="replace")
    return [decode_frame(line) for line in stdout.splitlines(keepends=True)], stderr.decode("utf-8", errors="replace")


def test_sidecar_builtin_methods_return_protocol_responses() -> None:
    frames, _stderr = run_sidecar(
        [
            request("sidecar.hello", {"supported_versions": [1]}, "hello"),
            request("sidecar.health", request_id="health"),
            request("sidecar.cancel", {"target_request_id": "missing"}, "cancel"),
            request("sidecar.shutdown", {"reason": "test"}, "shutdown"),
        ]
    )

    hello, health, cancel, shutdown = frames
    assert hello["ok"] is True
    assert hello["result"]["selected_protocol_version"] == 1
    assert hello["result"]["schema_hash"] == SCHEMA_HASH
    assert "catalog.v1" in hello["result"]["capabilities"]

    assert health["ok"] is True
    assert health["result"]["status"] == "ok"
    assert health["result"]["uptime_ms"] >= 0

    assert cancel["ok"] is False
    assert cancel["error"]["code"] == "sidecar.task_not_found"
    assert cancel["error"]["details"]["target_request_id"] == "missing"

    assert shutdown["ok"] is True
    assert shutdown["result"]["accepted_shutdown"] is True


def test_unmigrated_catalog_method_is_not_reported_as_missing() -> None:
    frames, _stderr = run_sidecar([request("config.get_all")])
    assert frames[0]["ok"] is False
    assert frames[0]["error"]["code"] == "sidecar.not_ready"


def test_unknown_method_returns_method_not_found() -> None:
    frames, _stderr = run_sidecar([request("unknown.method")])
    assert frames[0]["ok"] is False
    assert frames[0]["error"]["code"] == "rpc.method_not_found"


def test_sidecar_import_does_not_create_qapplication() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import importlib, json, sys; "
                "importlib.import_module('python_core.sidecar_main'); "
                "print(json.dumps({'qtwidgets': 'PySide6.QtWidgets' in sys.modules, 'pyside6': 'PySide6' in sys.modules}))"
            ),
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    loaded = json.loads(result.stdout)
    assert loaded == {"qtwidgets": False, "pyside6": False}


def test_sidecar_print_is_redirected_to_stderr() -> None:
    frames, stderr = run_sidecar(
        [request("sidecar.hello", {"supported_versions": [1]})],
        env={"YUMETSUKI_SIDECAR_TEST_PRINT": "debug from print"},
    )
    assert frames[0]["ok"] is True
    assert "debug from print" in stderr
