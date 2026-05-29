from __future__ import annotations

import argparse
import builtins
import json
import sys
from typing import BinaryIO, TextIO

from python_core.runtime_paths import RuntimePathError, RuntimePaths
from python_core.rpc.envelope import validate_request_envelope
from python_core.rpc.errors import make_error
from python_core.rpc.framing import ProtocolWriter, RpcFrameError, decode_frame
from python_core.rpc.registry import SidecarRuntime, build_default_registry


_ORIGINAL_PRINT = builtins.print


def redirect_print_to_stderr(stderr: TextIO | None = None) -> None:
    target = stderr or sys.stderr

    def stderr_print(*args: object, **kwargs: object) -> None:
        kwargs = {**kwargs, "file": target}
        _ORIGINAL_PRINT(*args, **kwargs)

    builtins.print = stderr_print


def run_stdio(
    runtime_paths: RuntimePaths,
    stdin: BinaryIO | None = None,
    stdout: BinaryIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    redirect_print_to_stderr(stderr)
    input_stream = stdin or sys.stdin.buffer
    writer = ProtocolWriter(stdout or sys.stdout.buffer)
    registry = build_default_registry()
    runtime = SidecarRuntime.create(runtime_paths)

    for line in input_stream:
        if not line.strip():
            continue
        try:
            raw = decode_frame(line)
            request = validate_request_envelope(raw)
            response = registry.dispatch(request, runtime)
        except RpcFrameError as exc:
            response = _orphan_error_response(exc.rpc_error.to_dict())
        except Exception as exc:  # noqa: BLE001 - sidecar must reply instead of crashing on bad input.
            response = _orphan_error_response(make_error("rpc.invalid_params", details={"summary": str(exc)}).to_dict())
        writer.write(response)
        for event in runtime.task_registry.event_publisher.drain():
            writer.write(event)
        if runtime.shutdown_requested:
            break
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Yumetsuki Python headless sidecar")
    parser.add_argument("--stdio", action="store_true", help="read and write NDJSON RPC frames on stdio")
    parser.add_argument("--runtime-paths-json", help="RuntimePaths JSON injected by Tauri")
    args = parser.parse_args(argv)

    try:
        runtime_paths = _runtime_paths_from_arg(args.runtime_paths_json)
    except (RuntimePathError, json.JSONDecodeError, TypeError) as exc:
        sys.stderr.write(f"sidecar runtime paths invalid: {exc}\n")
        return 2
    if args.stdio:
        return run_stdio(runtime_paths)
    sys.stderr.write("sidecar_main requires --stdio\n")
    return 2


def _runtime_paths_from_arg(value: str | None) -> RuntimePaths:
    if not value:
        return RuntimePaths.temporary()
    return RuntimePaths.from_json(json.loads(value), mode="dev")


def _orphan_error_response(error: dict[str, object]) -> dict[str, object]:
    return {
        "kind": "response",
        "request_id": "",
        "ok": False,
        "result": None,
        "error": error,
        "protocol_version": 1,
        "trace_id": "",
        "parent_trace_id": None,
        "session_id": "",
    }


if __name__ == "__main__":
    raise SystemExit(main())
