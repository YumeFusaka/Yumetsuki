from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class RpcErrorCode(str, Enum):
    RPC_INVALID_FRAME = "rpc.invalid_frame"
    RPC_INVALID_PARAMS = "rpc.invalid_params"
    RPC_METHOD_NOT_FOUND = "rpc.method_not_found"
    RPC_PROTOCOL_UNSUPPORTED = "rpc.protocol_unsupported"
    RPC_REQUEST_TIMEOUT = "rpc.request_timeout"
    RPC_DUPLICATE_TERMINAL = "rpc.duplicate_terminal"
    RPC_EVENT_OUT_OF_ORDER = "rpc.event_out_of_order"
    RPC_PAYLOAD_TOO_LARGE = "rpc.payload_too_large"
    SIDECAR_NOT_READY = "sidecar.not_ready"
    SIDECAR_RESTARTED = "sidecar.restarted"
    SIDECAR_TASK_NOT_FOUND = "sidecar.task_not_found"
    SIDECAR_SHUTDOWN_TIMEOUT = "sidecar.shutdown_timeout"
    CONFIG_VERSION_CONFLICT = "config.version_conflict"
    CONFIG_VALIDATION_FAILED = "config.validation_failed"
    CONFIG_WRITE_FAILED = "config.write_failed"
    CHARACTER_NOT_FOUND = "character.not_found"
    CHARACTER_CORE_FILE_PROTECTED = "character.core_file_protected"
    CHAT_CANCELLED = "chat.cancelled"
    CHAT_CONTEXT_UNAVAILABLE = "chat.context_unavailable"
    LLM_TIMEOUT = "llm.timeout"
    TOOL_CONFIRM_REQUIRED = "tool.confirm_required"
    TOOL_EXECUTION_FAILED = "tool.execution_failed"
    PLUGIN_WORKER_CRASHED = "plugin.worker_crashed"
    MCP_SERVER_UNAVAILABLE = "mcp.server_unavailable"
    TTS_TIMEOUT = "tts.timeout"
    STT_TIMEOUT = "stt.timeout"
    OCR_TIMEOUT = "ocr.timeout"
    LOGS_EXPORT_FAILED = "logs.export_failed"
    DIAGNOSTICS_REDACTION_FAILED = "diagnostics.redaction_failed"
    SECURITY_CONFIRM_TOKEN_INVALID = "security.confirm_token_invalid"
    SECURITY_PERMISSION_DENIED = "security.permission_denied"
    SECURITY_SHELL_COMMAND_DENIED = "security.shell_command_denied"
    FILESYSTEM_PATH_OUT_OF_SCOPE = "filesystem.path_out_of_scope"
    FILESYSTEM_HANDLE_EXPIRED = "filesystem.handle_expired"

    def __str__(self) -> str:
        return self.value


def _default_user_message(code: str) -> str:
    domain = code.split(".", 1)[0]
    return f"{domain} 操作失败，请查看平台日志。"


def _default_retryable(code: str) -> bool:
    return code.endswith("timeout") or code in {
        "sidecar.not_ready",
        "sidecar.restarted",
        "sidecar.task_not_found",
        "mcp.server_unavailable",
        "plugin.worker_crashed",
        "filesystem.handle_expired",
        "config.version_conflict",
        "config.write_failed",
        "config.validation_failed",
        "character.core_file_protected",
        "character.not_found",
        "chat.cancelled",
        "chat.context_unavailable",
        "llm.timeout",
        "tool.confirm_required",
        "tool.execution_failed",
        "plugin.worker_crashed",
        "mcp.server_unavailable",
        "tts.timeout",
        "stt.timeout",
        "ocr.timeout",
        "logs.export_failed",
        "diagnostics.redaction_failed",
        "security.confirm_token_invalid",
        "security.permission_denied",
        "security.shell_command_denied",
        "filesystem.path_out_of_scope",
    }


ERROR_METADATA: dict[str, dict[str, Any]] = {
    code.value: {
        "message": code.value,
        "user_message": _default_user_message(code.value),
        "retryable": _default_retryable(code.value),
        "details_schema": {"type": "object", "redaction": "redacted_object"},
        "redaction_policy": "default_sensitive_fields",
    }
    for code in RpcErrorCode
}


ERROR_CODES = set(ERROR_METADATA)


@dataclass(frozen=True)
class RpcError:
    code: str
    message: str
    user_message: str
    retryable: bool
    details: dict[str, Any]
    redaction_policy: str = "default_sensitive_fields"

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "user_message": self.user_message,
            "retryable": self.retryable,
            "details": self.details,
        }


def make_error(
    code: str | RpcErrorCode,
    message: str | None = None,
    retryable: bool | None = None,
    details: dict[str, Any] | None = None,
) -> RpcError:
    code_value = str(code)
    if code_value not in ERROR_METADATA:
        raise ValueError(f"unknown RPC error code: {code_value}")
    metadata = ERROR_METADATA[code_value]
    redacted_details = sanitize_error_details(details or {})
    return RpcError(
        code=code_value,
        message=message or metadata["message"],
        user_message=metadata["user_message"],
        retryable=metadata["retryable"] if retryable is None else retryable,
        details=redacted_details,
        redaction_policy=metadata["redaction_policy"],
    )


def sanitize_error_details(details: dict[str, Any]) -> dict[str, Any]:
    def sanitize(value: Any, key: str = "") -> Any:
        lowered = key.lower()
        if any(marker in lowered for marker in ("api_key", "authorization", "cookie", "token")):
            return "[redacted]"
        if isinstance(value, dict):
            return {child_key: sanitize(child_value, child_key) for child_key, child_value in value.items()}
        if isinstance(value, list):
            return [sanitize(item, key) for item in value]
        if isinstance(value, str) and _looks_sensitive(value):
            return "[redacted]"
        return value

    return sanitize(details)


def assert_details_are_redacted(details: dict[str, Any]) -> None:
    sanitized = sanitize_error_details(details)
    if sanitized != details:
        raise ValueError("RpcError.details contains unredacted sensitive data")


def _looks_sensitive(value: str) -> bool:
    lowered = value.lower()
    if lowered.startswith("sk-") or "authorization:" in lowered or "bearer " in lowered:
        return True
    if "cookie:" in lowered or "api_key=" in lowered or "token=" in lowered:
        return True
    if "c:/users/" in lowered or "c:\\users\\" in lowered:
        return True
    if any(marker in lowered for marker in ("http://10.", "http://192.168.", "http://172.16.", "http://127.")):
        return True
    return False
