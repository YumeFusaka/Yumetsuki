from __future__ import annotations

import json
import re
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = PROJECT_ROOT / "python_core" / "rpc" / "schema" / "catalog.json"
RUST_RPC_PATH = PROJECT_ROOT / "apps" / "desktop" / "src-tauri" / "src" / "rpc.rs"
TS_RPC_PATH = PROJECT_ROOT / "apps" / "desktop" / "frontend" / "src" / "client" / "types" / "rpc.ts"
PYTHON_ERRORS_PATH = PROJECT_ROOT / "python_core" / "rpc" / "errors.py"


def main() -> int:
    errors: list[str] = []
    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    method_names = {item["method"] for item in catalog["methods"]}
    event_types = {item["type"] for item in catalog["events"]}
    error_codes = set(catalog["errors"])

    errors.extend(_check_catalog_shape(catalog, method_names, event_types))
    errors.extend(_check_rust_contract())
    errors.extend(_check_typescript_contract(method_names, event_types))
    errors.extend(_check_python_error_catalog(error_codes))

    if errors:
        sys.stderr.write("RPC schema contract 检查失败：\n")
        for error in errors:
            sys.stderr.write(f"- {error}\n")
        return 1
    print(
        "RPC schema contract 检查通过："
        f"{len(method_names)} methods, {len(event_types)} events, {len(error_codes)} errors。"
    )
    return 0


def _check_catalog_shape(catalog: dict, method_names: set[str], event_types: set[str]) -> list[str]:
    errors: list[str] = []
    if catalog.get("protocol_version") != 1:
        errors.append("catalog.protocol_version 必须为 1")
    if catalog.get("min_compatible_protocol_version") != 1:
        errors.append("catalog.min_compatible_protocol_version 必须为 1")
    if "sidecar.cancel" not in method_names:
        errors.append("catalog 必须包含唯一取消 wire method sidecar.cancel")
    extra_cancel = [
        method
        for method in method_names
        if method != "sidecar.cancel" and (method.endswith(".cancel") or method.startswith("cancel_"))
    ]
    if extra_cancel:
        errors.append(f"存在除 sidecar.cancel 外的取消 wire method：{sorted(extra_cancel)}")
    if "security.confirm_required" in method_names:
        errors.append("security.confirm_required 必须是 event，不能是 method")
    if "security.confirm_required" not in event_types:
        errors.append("catalog events 必须包含 security.confirm_required")
    for method in catalog["methods"]:
        name = method["method"]
        if method.get("long_task") is True and "accepted" not in method:
            errors.append(f"{name} 长任务必须声明 accepted")
        if method.get("long_task") is True and "result" in method:
            errors.append(f"{name} 长任务不得声明同步 result")
        if method.get("long_task") is False and "result" not in method:
            errors.append(f"{name} 短任务必须声明 result")
        missing_events = set(method.get("events", [])) - event_types
        if missing_events:
            errors.append(f"{name} 引用了不存在的 event：{sorted(missing_events)}")
    return errors


def _check_rust_contract() -> list[str]:
    text = RUST_RPC_PATH.read_text(encoding="utf-8")
    required_snippets = [
        "pub struct RpcContext",
        "pub struct RequestEnvelope",
        "pub struct ResponseEnvelope",
        "pub struct EventEnvelope",
        "pub struct RpcError",
        "pub fn validate_no_legacy_id",
        "request_id",
        "trace_id",
        "parent_trace_id",
        "session_id",
        "protocol_version",
    ]
    return [f"Rust RPC contract 缺少片段：{snippet}" for snippet in required_snippets if snippet not in text]


def _check_typescript_contract(method_names: set[str], event_types: set[str]) -> list[str]:
    text = TS_RPC_PATH.read_text(encoding="utf-8")
    errors: list[str] = []
    for snippet in [
        "export type RpcMethod",
        "export type RpcEventType",
        "request_id",
        "trace_id",
        "parent_trace_id",
        "session_id",
        "protocol_version",
        "export interface RpcError",
    ]:
        if snippet not in text:
            errors.append(f"TypeScript RPC contract 缺少片段：{snippet}")

    ts_methods = set(re.findall(r'"([a-z]+\.[a-zA-Z0-9_.]+)"', _extract_union(text, "RpcMethod")))
    missing_required_methods = {"sidecar.hello", "sidecar.health", "sidecar.cancel", "config.get_all", "chat.send", "logs.query"} - ts_methods
    if missing_required_methods:
        errors.append(f"TypeScript RpcMethod 缺少首版必需 method：{sorted(missing_required_methods)}")
    unknown_methods = ts_methods - method_names
    if unknown_methods:
        errors.append(f"TypeScript RpcMethod 包含 catalog 外 method：{sorted(unknown_methods)}")

    ts_events = set(re.findall(r'"([a-z]+\.[a-zA-Z0-9_.]+)"', _extract_union(text, "RpcEventType")))
    unknown_events = ts_events - event_types
    if unknown_events:
        errors.append(f"TypeScript RpcEventType 包含 catalog 外 event：{sorted(unknown_events)}")
    return errors


def _extract_union(text: str, name: str) -> str:
    match = re.search(rf"export\s+type\s+{name}\s*=(?P<body>.*?);", text, re.S)
    return match.group("body") if match else ""


def _check_python_error_catalog(error_codes: set[str]) -> list[str]:
    text = PYTHON_ERRORS_PATH.read_text(encoding="utf-8")
    missing = [code for code in sorted(error_codes) if code not in text]
    return [f"Python ERROR_CATALOG 缺少 catalog 错误码：{code}" for code in missing]


if __name__ == "__main__":
    raise SystemExit(main())
