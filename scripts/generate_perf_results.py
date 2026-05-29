from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import psutil


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BUNDLE = ROOT / "apps" / "desktop" / "src-tauri" / "target" / "release" / "bundle"
DEFAULT_OUTPUT = ROOT / "apps" / "desktop" / "perf" / "results.json"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def sha256_text(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def encode_frame(payload: dict[str, object]) -> bytes:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8") + b"\n"


def read_frame(stream) -> dict[str, object]:
    line = stream.readline()
    if not line:
        raise RuntimeError("sidecar 提前退出")
    return json.loads(line.decode("utf-8"))


def spawn_sidecar() -> subprocess.Popen[bytes]:
    return subprocess.Popen(
        [sys.executable, "-m", "python_core.sidecar_main", "--stdio"],
        cwd=ROOT,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )


def send_request(proc: subprocess.Popen[bytes], payload: dict[str, object], terminal_event_type: str | None = None) -> tuple[float, dict[str, object], list[dict[str, object]]]:
    assert proc.stdin is not None
    assert proc.stdout is not None
    started = time.perf_counter()
    proc.stdin.write(encode_frame(payload))
    proc.stdin.flush()
    response: dict[str, object] | None = None
    events: list[dict[str, object]] = []
    first_event_ms = 0.0
    terminal_types = {"chat.done", "tts.done", "stt.done", "sidecar.exiting"}
    while True:
        frame = read_frame(proc.stdout)
        if frame.get("kind") == "response" and frame.get("request_id") == payload["request_id"]:
            response = frame
            if terminal_event_type is None:
                break
        elif frame.get("kind") == "event" and frame.get("request_id") == payload["request_id"]:
            events.append(frame)
            if terminal_event_type and frame.get("type") == terminal_event_type and first_event_ms == 0.0:
                first_event_ms = (time.perf_counter() - started) * 1000.0
            if frame.get("type") in terminal_types and payload["method"] != "sidecar.hello":
                break
        if response is not None and terminal_event_type is None:
            break
    if response is None:
        raise RuntimeError(f"{payload['request_id']} 没有响应")
    return ((first_event_ms or (time.perf_counter() - started) * 1000.0), response, events)


def shutdown_sidecar(proc: subprocess.Popen[bytes]) -> None:
    try:
        if proc.poll() is None and proc.stdin is not None and proc.stdout is not None:
            payload = {
                "kind": "request",
                "request_id": "req_shutdown_perf",
                "method": "sidecar.shutdown",
                "params": {"reason": "perf"},
                "protocol_version": 1,
                "trace_id": "trace_perf",
                "parent_trace_id": None,
                "session_id": "sess_perf",
                "deadline_ms": 30000,
            }
            try:
                proc.stdin.write(encode_frame(payload))
                proc.stdin.flush()
                while True:
                    frame = read_frame(proc.stdout)
                    if frame.get("kind") == "response" and frame.get("request_id") == payload["request_id"]:
                        break
            except Exception:
                pass
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=10)


def build_payload(method: str, request_id: str, params: dict[str, object]) -> dict[str, object]:
    return {
        "kind": "request",
        "request_id": request_id,
        "method": method,
        "params": params,
        "protocol_version": 1,
        "trace_id": f"trace_{request_id}",
        "parent_trace_id": None,
        "session_id": "sess_perf",
        "deadline_ms": 30000,
    }


def measure_sidecar_startup() -> tuple[float, float, float, float, float]:
    proc = spawn_sidecar()
    try:
        hello_ms, response, _events = send_request(
            proc,
            build_payload("sidecar.hello", "req_perf_hello", {"supported_protocol_versions": [1]}),
        )
        assert response["ok"] is True
        proc_ps = psutil.Process(proc.pid)
        proc_ps.cpu_percent(interval=None)
        time.sleep(0.2)
        idle_cpu_percent = proc_ps.cpu_percent(interval=None)
        sidecar_memory_mib = proc_ps.memory_info().rss / (1024 * 1024)
        chat_ms, chat_response, chat_events = send_request(
            proc,
            build_payload("chat.send", "req_perf_chat", {"text": "hello", "session_id": "sess_perf"}),
            terminal_event_type="chat.delta",
        )
        assert chat_response["ok"] is True
        assert any(event["type"] == "chat.delta" for event in chat_events)
        tts_ms, tts_response, tts_events = send_request(
            proc,
            build_payload(
                "tts.synthesize",
                "req_perf_tts",
                {"text": "你好", "voice_config_ref": "local-default", "session_id": "sess_perf"},
            ),
            terminal_event_type="tts.segment",
        )
        assert tts_response["ok"] is True
        assert any(event["type"] == "tts.segment" for event in tts_events)
        return hello_ms, idle_cpu_percent, sidecar_memory_mib, chat_ms, tts_ms
    finally:
        shutdown_sidecar(proc)


def measure_cold_hello_ms() -> float:
    proc = spawn_sidecar()
    try:
        hello_ms, response, _events = send_request(
            proc,
            build_payload("sidecar.hello", "req_perf_cold", {"supported_protocol_versions": [1]}),
        )
        assert response["ok"] is True
        return hello_ms
    finally:
        shutdown_sidecar(proc)


def measure_logs_fps() -> float:
    from python_core.rpc.event_publisher import RpcEventPublisher
    from python_core.rpc.context import RpcContext

    publisher = RpcEventPublisher()
    context = RpcContext(
        request_id="req_logs_perf",
        trace_id="trace_logs_perf",
        parent_trace_id=None,
        session_id="sess_perf",
        deadline_ms=30000,
    )
    started = time.perf_counter()
    for index in range(10_000):
        publisher.publish("system.log", context, {"index": index, "message": "x"})
    elapsed = time.perf_counter() - started
    return 10_000 / max(elapsed, 0.001)


def path_size(path: Path) -> int:
    if path.is_file():
        return path.stat().st_size
    return sum(item.stat().st_size for item in path.rglob("*") if item.is_file())


def main() -> int:
    parser = argparse.ArgumentParser(description="生成 Yumetsuki 性能结果文件")
    parser.add_argument("--bundle", type=Path, default=DEFAULT_BUNDLE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    bundle = args.bundle if args.bundle.is_absolute() else ROOT / args.bundle
    output = args.output if args.output.is_absolute() else ROOT / args.output
    sidecar = bundle / "resources" / "sidecar.exe"
    frontend = bundle / "frontend"
    resources = bundle / "resources"

    if not bundle.is_dir():
        raise SystemExit(f"bundle 缺失: {bundle}")
    if not sidecar.is_file():
        raise SystemExit(f"sidecar artifact 缺失: {sidecar}")
    if not frontend.is_dir():
        raise SystemExit(f"frontend 目录缺失: {frontend}")
    if not resources.is_dir():
        raise SystemExit(f"resources 目录缺失: {resources}")

    cold_startup_ms = measure_cold_hello_ms()
    sidecar_hello_ms, idle_cpu_percent, sidecar_memory_mib, chat_first_token_ms, tts_first_segment_ms = measure_sidecar_startup()
    logs_10k_fps = measure_logs_fps()
    frontend_bundle_size_bytes = path_size(frontend)
    sidecar_artifact_size_bytes = sidecar.stat().st_size
    resource_size_bytes = path_size(resources)
    bundle_size_bytes = path_size(bundle)
    installer_size_bytes = bundle_size_bytes

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "generated_by": {
            "manual": False,
            "sources": ["e2e:startup", "e2e:stress", "diagnostics_perf", "release_scan"],
            "commands": [
                "pnpm e2e:startup",
                "pnpm e2e:stress",
                "python scripts/check_release_manifest.py --bundle apps/desktop/src-tauri/target/release/bundle",
            ],
        },
        "machine": {
            "platform": platform.platform(),
            "python": platform.python_version(),
        },
        "metrics": {
            "cold_startup_ms": round(cold_startup_ms, 2),
            "warm_startup_ms": round(sidecar_hello_ms, 2),
            "sidecar_hello_ms": round(sidecar_hello_ms, 2),
            "idle_cpu_percent": round(idle_cpu_percent, 2),
            "sidecar_memory_mib": round(sidecar_memory_mib, 2),
            "chat_first_token_ms": round(chat_first_token_ms, 2),
            "tts_first_segment_ms": round(tts_first_segment_ms, 2),
            "logs_10k_fps": round(logs_10k_fps, 2),
            "frontend_bundle_size_bytes": frontend_bundle_size_bytes,
            "sidecar_artifact_size_bytes": sidecar_artifact_size_bytes,
            "resource_size_bytes": resource_size_bytes,
            "installer_size_bytes": installer_size_bytes,
            "bundle_size_bytes": bundle_size_bytes,
        },
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"性能结果已生成: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
