from __future__ import annotations

from collections import Counter
from typing import Any


ALLOWED_STOP_METHODS = {"proactive.stop", "stt.stop_recording", "mcp.stop_server"}
SUPERVISOR_OR_SECURITY_EVENTS = {
    "security.confirm_required",
    "sidecar.crashed",
    "sidecar.restarted",
}
REQUIRED_FIELD_KEYS = {"type", "required", "redaction"}


def method_names(catalog: dict[str, Any]) -> list[str]:
    return [method["method"] for method in catalog.get("methods", [])]


def event_names(catalog: dict[str, Any]) -> list[str]:
    return [event["event"] for event in catalog.get("events", [])]


def _validate_field_schema(path: str, schema: Any, errors: list[str]) -> None:
    if not isinstance(schema, dict):
        errors.append(f"{path} 必须是对象 schema")
        return
    missing = REQUIRED_FIELD_KEYS - set(schema)
    if missing:
        errors.append(f"{path} 缺少字段：{', '.join(sorted(missing))}")
    if "nullable" not in schema and "default" not in schema:
        errors.append(f"{path} 必须声明 nullable 或 default")
    if schema.get("type") == "literal" and "value" not in schema:
        errors.append(f"{path} literal 必须声明 value")


def _validate_schema_map(path: str, schema_map: Any, errors: list[str]) -> None:
    if not isinstance(schema_map, dict):
        errors.append(f"{path} 必须是字段 schema map")
        return
    for field, schema in schema_map.items():
        _validate_field_schema(f"{path}.{field}", schema, errors)


def validate_catalog(catalog: dict[str, Any], known_error_codes: set[str] | None = None) -> list[str]:
    errors: list[str] = []
    for key in ("schema_version", "protocol_version", "min_compatible_protocol_version", "generated_from_design"):
        if key not in catalog:
            errors.append(f"catalog 缺少顶层字段：{key}")

    methods = catalog.get("methods")
    events = catalog.get("events")
    if not isinstance(methods, list) or not methods:
        errors.append("catalog.methods 必须是非空数组")
        methods = []
    if not isinstance(events, list) or not events:
        errors.append("catalog.events 必须是非空数组")
        events = []

    method_counter = Counter(method_names(catalog))
    event_counter = Counter(event_names(catalog))
    for name, count in sorted(method_counter.items()):
        if count > 1:
            errors.append(f"重复 method：{name}")
    for name, count in sorted(event_counter.items()):
        if count > 1:
            errors.append(f"重复 event：{name}")

    event_set = set(event_counter)
    referenced_events: set[str] = set()
    for method in methods:
        name = method.get("method")
        if not name:
            errors.append("method 缺少 method 字段")
            continue
        if name != "sidecar.cancel" and ("cancel" in name or name.endswith(".cancel")):
            errors.append(f"{name} 是非法取消 method，唯一允许的是 sidecar.cancel")
        if name.endswith(".stop") or name in ALLOWED_STOP_METHODS:
            if name not in ALLOWED_STOP_METHODS:
                errors.append(f"{name} 不是允许的业务 stop method")
            if method.get("long_task") is not False:
                errors.append(f"{name} 必须 long_task=false")
            if method.get("cancels_request") is not False:
                errors.append(f"{name} 必须 cancels_request=false")
            if "request_id" in method.get("params", {}):
                errors.append(f"{name} 不得接收任意 request_id")
            if any(str(event).endswith(".cancelled") for event in method.get("events", [])):
                errors.append(f"{name} 不得发送 cancelled 终态事件")

        for key in ("long_task", "params", "events", "errors", "redaction"):
            if key not in method:
                errors.append(f"{name} 缺少字段：{key}")
        if not method.get("errors"):
            errors.append(f"{name} errors 不得为空")
        if not method.get("redaction"):
            errors.append(f"{name} redaction 不得为空")
        _validate_schema_map(f"{name}.params", method.get("params", {}), errors)
        if method.get("long_task") is True:
            if "accepted" not in method:
                errors.append(f"{name} long_task=true 必须声明 accepted")
            if "result" in method:
                errors.append(f"{name} long_task=true 不得声明同步 result")
            _validate_schema_map(f"{name}.accepted", method.get("accepted", {}), errors)
        elif method.get("long_task") is False:
            if "result" not in method:
                errors.append(f"{name} long_task=false 必须声明 result")
            if "accepted" in method:
                errors.append(f"{name} long_task=false 不得声明 accepted")
            _validate_schema_map(f"{name}.result", method.get("result", {}), errors)
        else:
            errors.append(f"{name} long_task 必须是布尔值")
        for event in method.get("events", []):
            referenced_events.add(event)
            if event not in event_set:
                errors.append(f"{name} 引用了未声明事件：{event}")

    for event in events:
        name = event.get("event")
        if not name:
            errors.append("event 缺少 event 字段")
            continue
        if name == "security.confirm_required" and event.get("event_only") is not True:
            errors.append("security.confirm_required 必须标记 event_only=true")
        if not event.get("redaction"):
            errors.append(f"{name} redaction 不得为空")
        _validate_schema_map(f"{name}.payload", event.get("payload", {}), errors)
        if event.get("terminal") is True:
            payload = event.get("payload", {})
            for field in ("state", "summary", "error"):
                if field not in payload:
                    errors.append(f"{name} 终态事件缺少 payload.{field}")

    orphan_events = event_set - referenced_events - SUPERVISOR_OR_SECURITY_EVENTS
    if orphan_events:
        errors.append("存在未被 method 引用的孤儿事件：" + ", ".join(sorted(orphan_events)))

    if "security.confirm_required" in method_counter:
        errors.append("security.confirm_required 不得出现在 method catalog")
    if "sidecar.cancel" not in method_counter:
        errors.append("缺少唯一取消 method：sidecar.cancel")

    if known_error_codes is not None:
        known_domains = {code.split(".", 1)[0] for code in known_error_codes}
        catalog_errors = set(catalog.get("errors", []))
        missing_codes = catalog_errors - known_error_codes
        if missing_codes:
            errors.append("catalog.errors 中存在 errors.py 未声明错误码：" + ", ".join(sorted(missing_codes)))
        for method in methods:
            for error in method.get("errors", []):
                if error.endswith(".*"):
                    domain = error[:-2]
                    if domain not in known_domains:
                        errors.append(f"{method['method']} 引用未知错误域：{error}")
                elif error not in known_error_codes:
                    errors.append(f"{method['method']} 引用未知错误码：{error}")

    return errors
