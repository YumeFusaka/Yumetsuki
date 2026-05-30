from __future__ import annotations

import argparse
import builtins
import json
import os
import sys
import time
from typing import BinaryIO, Iterable

from .runtime_paths import RuntimePaths
from .rpc.envelope import RequestEnvelope, validate_request_envelope
from .rpc.errors import make_error, sanitize_error_details
from .rpc.framing import FrameDecodeError, decode_frame, encode_frame
from .rpc.registry import RegistryContext, dispatch_method
from .rpc.shutdown import ShutdownCoordinator
from .rpc.tasks import TaskRegistry


_PROTOCOL_STDOUT_GUARD = None
_PROTOCOL_BUFFER_GUARD = None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stdio", action="store_true")
    parser.add_argument("--runtime-paths-json", default="{}")
    args = parser.parse_args(argv)
    if not args.stdio:
        parser.error("sidecar_main currently requires --stdio")

    global _PROTOCOL_STDOUT_GUARD, _PROTOCOL_BUFFER_GUARD
    _PROTOCOL_STDOUT_GUARD = sys.stdout
    _PROTOCOL_BUFFER_GUARD = os.fdopen(os.dup(sys.stdout.fileno()), "wb", buffering=0)
    redirect_stdout_to_stderr()
    runtime_paths = _load_runtime_paths(args.runtime_paths_json)
    task_registry = TaskRegistry()
    shutdown = ShutdownCoordinator(task_registry=task_registry)
    context = RegistryContext(
        started_at=time.monotonic(),
        task_registry=task_registry,
        runtime_paths_ready=runtime_paths is not None,
        shutdown_coordinator=shutdown,
    )
    _run_stdio(sys.stdin.buffer, _PROTOCOL_BUFFER_GUARD, context)
    return 0


def redirect_stdout_to_stderr() -> None:
    original_print = builtins.print

    def stderr_print(*args: object, **kwargs: object) -> None:
        kwargs.setdefault("file", sys.stderr)
        original_print(*args, **kwargs)

    builtins.print = stderr_print
    sys.stdout = sys.stderr


def _run_stdio(stdin: BinaryIO, protocol_stdout: BinaryIO, context: RegistryContext) -> None:
    for line in stdin:
        _emit_test_noise()
        try:
            payload = decode_frame(line)
            request = validate_request_envelope(payload)
            result = dispatch_method(request.method, request.params, context)
            response = _response_from_result(request, result)
        except (FrameDecodeError, TypeError, ValueError) as exc:
            response = _invalid_frame_response(str(exc))
        protocol_stdout.write(encode_frame(response))
        protocol_stdout.flush()


def _response_from_result(request: RequestEnvelope, result: dict[str, object]) -> dict[str, object]:
    ok = bool(result["ok"])
    return {
        "kind": "response",
        "protocol_version": request.protocol_version,
        "request_id": request.request_id,
        "trace_id": request.trace_id,
        "parent_trace_id": request.parent_trace_id,
        "session_id": request.session_id,
        "ok": ok,
        "result": result.get("result") if ok else None,
        "error": None if ok else result["error"],
    }


def _invalid_frame_response(message: str) -> dict[str, object]:
    return {
        "kind": "response",
        "protocol_version": 1,
        "request_id": "invalid",
        "trace_id": "invalid",
        "parent_trace_id": None,
        "session_id": "invalid",
        "ok": False,
        "result": None,
        "error": make_error("rpc.invalid_frame", message=message).to_dict(),
    }


def _load_runtime_paths(raw_json: str) -> RuntimePaths | None:
    data = json.loads(raw_json)
    if not data:
        return None
    if not isinstance(data, dict):
        raise ValueError("--runtime-paths-json must be an object")
    return RuntimePaths.from_json(data)


def _emit_test_noise() -> None:
    message = os.environ.get("YUMETSUKI_SIDECAR_TEST_PRINT")
    if message:
        sidecar_stderr_logger(message)
    if os.environ.get("YUMETSUKI_SIDECAR_TEST_FLOOD"):
        for index in range(20):
            sidecar_stderr_logger(f"flood-line-{index}")
    if os.environ.get("YUMETSUKI_SIDECAR_TEST_SENSITIVE_LOG"):
        _write_diagnostic(
            [
                "Authorization: Bearer sk-test-token",
                "path=C:\\Users\\Alice\\secret",
                "url=http://10.0.0.1/private",
            ]
        )


def _write_diagnostic(lines: Iterable[str]) -> None:
    for line in lines:
        redacted = sanitize_error_details({"message": line})["message"]
        sidecar_stderr_logger(redacted)


def sidecar_stderr_logger(message: object) -> None:
    sys.stderr.write(f"{message}\n")
    sys.stderr.flush()


if __name__ == "__main__":
    raise SystemExit(main())
