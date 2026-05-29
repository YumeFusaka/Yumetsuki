from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any


class RpcErrorCode:
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
    SIDECAR_BUSY = "sidecar.busy"
    SIDECAR_TASK_NOT_FOUND = "sidecar.task_not_found"
    SIDECAR_SHUTDOWN_TIMEOUT = "sidecar.shutdown_timeout"

    CONFIG_VERSION_CONFLICT = "config.version_conflict"
    CONFIG_VALIDATION_FAILED = "config.validation_failed"
    CONFIG_WRITE_FAILED = "config.write_failed"

    CHAT_CANCELLED = "chat.cancelled"
    CHAT_CONTEXT_UNAVAILABLE = "chat.context_unavailable"

    LLM_TIMEOUT = "llm.timeout"
    TTS_TIMEOUT = "tts.timeout"
    STT_TIMEOUT = "stt.timeout"
    OCR_TIMEOUT = "ocr.timeout"

    PLUGIN_WORKER_CRASHED = "plugin.worker_crashed"
    MCP_SERVER_UNAVAILABLE = "mcp.server_unavailable"

    TOOL_CONFIRM_REQUIRED = "tool.confirm_required"
    TOOL_EXECUTION_FAILED = "tool.execution_failed"

    SECURITY_CONFIRM_TOKEN_INVALID = "security.confirm_token_invalid"
    SECURITY_PERMISSION_DENIED = "security.permission_denied"
    SECURITY_SHELL_COMMAND_DENIED = "security.shell_command_denied"

    FILESYSTEM_PATH_OUT_OF_SCOPE = "filesystem.path_out_of_scope"
    FILESYSTEM_HANDLE_EXPIRED = "filesystem.handle_expired"

    LOGS_QUERY_FAILED = "logs.query_failed"
    DIAGNOSTICS_REDACTION_FAILED = "diagnostics.redaction_failed"
    DIAGNOSTICS_WRITE_FAILED = "diagnostics.write_failed"


ERROR_CATALOG: dict[str, dict[str, Any]] = {
    RpcErrorCode.RPC_INVALID_FRAME: {
        "message": "RPC frame is invalid.",
        "user_message": "通信数据格式错误，请重试或重启应用。",
        "retryable": False,
    },
    RpcErrorCode.RPC_INVALID_PARAMS: {
        "message": "RPC params are invalid.",
        "user_message": "请求参数不完整或格式错误。",
        "retryable": False,
    },
    RpcErrorCode.RPC_METHOD_NOT_FOUND: {
        "message": "RPC method is not registered.",
        "user_message": "当前版本暂不支持这个操作。",
        "retryable": False,
    },
    RpcErrorCode.RPC_PROTOCOL_UNSUPPORTED: {
        "message": "RPC protocol version is unsupported.",
        "user_message": "桌面壳与 Python 内核协议版本不兼容。",
        "retryable": False,
    },
    RpcErrorCode.RPC_REQUEST_TIMEOUT: {
        "message": "RPC request deadline reached.",
        "user_message": "请求超时，可以稍后重试。",
        "retryable": True,
    },
    RpcErrorCode.RPC_DUPLICATE_TERMINAL: {
        "message": "Task terminal event was emitted more than once.",
        "user_message": "任务状态异常，请查看平台日志。",
        "retryable": False,
    },
    RpcErrorCode.RPC_EVENT_OUT_OF_ORDER: {
        "message": "RPC event sequence is out of order.",
        "user_message": "事件顺序异常，请重试当前操作。",
        "retryable": False,
    },
    RpcErrorCode.RPC_PAYLOAD_TOO_LARGE: {
        "message": "RPC payload is too large.",
        "user_message": "内容过大，已拒绝通过实时通道传输。",
        "retryable": False,
    },
    RpcErrorCode.SIDECAR_NOT_READY: {
        "message": "Sidecar service is not ready.",
        "user_message": "Python 内核尚未准备好。",
        "retryable": True,
    },
    RpcErrorCode.SIDECAR_RESTARTED: {
        "message": "Sidecar was restarted.",
        "user_message": "Python 内核已重启，请重试当前操作。",
        "retryable": True,
    },
    RpcErrorCode.SIDECAR_BUSY: {
        "message": "Sidecar is busy.",
        "user_message": "Python 内核正在处理其他请求，请稍后重试。",
        "retryable": True,
    },
    RpcErrorCode.SIDECAR_TASK_NOT_FOUND: {
        "message": "Task request_id was not found.",
        "user_message": "目标任务不存在或已被清理。",
        "retryable": False,
    },
    RpcErrorCode.SIDECAR_SHUTDOWN_TIMEOUT: {
        "message": "Sidecar shutdown timed out.",
        "user_message": "Python 内核关闭超时，应用会尝试强制退出。",
        "retryable": True,
    },
    RpcErrorCode.CONFIG_VERSION_CONFLICT: {
        "message": "Config base version is stale.",
        "user_message": "配置已被更新，请刷新后重试。",
        "retryable": True,
    },
    RpcErrorCode.CONFIG_VALIDATION_FAILED: {
        "message": "Config validation failed.",
        "user_message": "配置校验失败，请检查输入。",
        "retryable": False,
    },
    RpcErrorCode.CONFIG_WRITE_FAILED: {
        "message": "Config write failed.",
        "user_message": "配置保存失败，已保留当前草稿。",
        "retryable": True,
    },
    RpcErrorCode.CHAT_CANCELLED: {
        "message": "Chat request was cancelled.",
        "user_message": "已停止本次回复。",
        "retryable": True,
    },
    RpcErrorCode.CHAT_CONTEXT_UNAVAILABLE: {
        "message": "Chat context is unavailable.",
        "user_message": "当前会话上下文不可用，请稍后重试。",
        "retryable": True,
    },
    RpcErrorCode.LLM_TIMEOUT: {
        "message": "LLM request timed out.",
        "user_message": "模型回复超时，可以重试。",
        "retryable": True,
    },
    RpcErrorCode.TTS_TIMEOUT: {
        "message": "TTS request timed out.",
        "user_message": "语音合成超时，可以重试。",
        "retryable": True,
    },
    RpcErrorCode.STT_TIMEOUT: {
        "message": "STT request timed out.",
        "user_message": "语音识别超时，可以重试。",
        "retryable": True,
    },
    RpcErrorCode.OCR_TIMEOUT: {
        "message": "OCR request timed out.",
        "user_message": "屏幕识别超时，可以重试。",
        "retryable": True,
    },
    RpcErrorCode.PLUGIN_WORKER_CRASHED: {
        "message": "Plugin worker crashed.",
        "user_message": "插件进程异常退出，可以重试或查看日志。",
        "retryable": True,
    },
    RpcErrorCode.MCP_SERVER_UNAVAILABLE: {
        "message": "MCP server is unavailable.",
        "user_message": "MCP 服务不可用，请检查配置后重试。",
        "retryable": True,
    },
    RpcErrorCode.TOOL_CONFIRM_REQUIRED: {
        "message": "Tool call requires explicit confirmation.",
        "user_message": "该工具调用需要确认后才能执行。",
        "retryable": False,
    },
    RpcErrorCode.TOOL_EXECUTION_FAILED: {
        "message": "Tool execution failed.",
        "user_message": "工具执行失败，请查看平台日志。",
        "retryable": True,
    },
    RpcErrorCode.SECURITY_CONFIRM_TOKEN_INVALID: {
        "message": "Confirmation token is invalid.",
        "user_message": "确认令牌无效或已过期。",
        "retryable": False,
    },
    RpcErrorCode.SECURITY_PERMISSION_DENIED: {
        "message": "Permission was denied.",
        "user_message": "权限不足，操作已被拒绝。",
        "retryable": False,
    },
    RpcErrorCode.SECURITY_SHELL_COMMAND_DENIED: {
        "message": "Shell command is denied.",
        "user_message": "该命令形式存在风险，已拒绝执行。",
        "retryable": False,
    },
    RpcErrorCode.FILESYSTEM_PATH_OUT_OF_SCOPE: {
        "message": "Path is outside allowed scope.",
        "user_message": "路径不在允许范围内。",
        "retryable": False,
    },
    RpcErrorCode.FILESYSTEM_HANDLE_EXPIRED: {
        "message": "Handle has expired.",
        "user_message": "临时资源已过期，请重新执行操作。",
        "retryable": True,
    },
    RpcErrorCode.LOGS_QUERY_FAILED: {
        "message": "Log query failed.",
        "user_message": "日志查询失败，请稍后重试。",
        "retryable": True,
    },
    RpcErrorCode.DIAGNOSTICS_REDACTION_FAILED: {
        "message": "Diagnostic redaction failed.",
        "user_message": "诊断导出脱敏失败，已阻止导出。",
        "retryable": False,
    },
    RpcErrorCode.DIAGNOSTICS_WRITE_FAILED: {
        "message": "Diagnostic write failed.",
        "user_message": "诊断报告写入失败。",
        "retryable": True,
    },
}

_SENSITIVE_KEY_RE = re.compile(
    r"(api[_-]?key|authorization|cookie|token|secret|password|credential)",
    re.IGNORECASE,
)
_SENSITIVE_TEXT_RE = re.compile(
    r"(sk-[A-Za-z0-9_\-]{8,}|Bearer\s+[A-Za-z0-9._\-]+|Authorization\s*:|Cookie\s*:)",
    re.IGNORECASE,
)
_WINDOWS_USER_PATH_RE = re.compile(r"[A-Za-z]:[\\/]+Users[\\/]+[^\\/]+", re.IGNORECASE)
_PRIVATE_URL_RE = re.compile(
    r"https?://(?:(?:localhost)|(?:127\.)|(?:10\.)|(?:192\.168\.)|(?:172\.(?:1[6-9]|2\d|3[0-1])\.))[^ \t\r\n]*",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class RpcError:
    code: str
    message: str
    user_message: str
    retryable: bool
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "user_message": self.user_message,
            "retryable": self.retryable,
            "details": self.details,
        }


def redact_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _redact_by_key(key, item) for key, item in value.items()}
    if isinstance(value, list):
        return [redact_value(item) for item in value]
    if isinstance(value, tuple):
        return [redact_value(item) for item in value]
    if isinstance(value, str):
        return _redact_text(value)
    return value


def contains_unredacted_sensitive_value(value: Any) -> bool:
    if isinstance(value, dict):
        for key, item in value.items():
            if _SENSITIVE_KEY_RE.search(str(key)):
                if item not in (None, "", False, "<redacted>") and not _looks_masked(str(item)):
                    return True
            if contains_unredacted_sensitive_value(item):
                return True
        return False
    if isinstance(value, (list, tuple)):
        return any(contains_unredacted_sensitive_value(item) for item in value)
    if isinstance(value, str):
        if _SENSITIVE_TEXT_RE.search(value):
            return True
        if _WINDOWS_USER_PATH_RE.search(value):
            return True
        if _PRIVATE_URL_RE.search(value):
            return True
    return False


def make_error(
    code: str,
    message: str | None = None,
    retryable: bool | None = None,
    details: dict[str, Any] | None = None,
    user_message: str | None = None,
) -> RpcError:
    if code not in ERROR_CATALOG:
        raise ValueError(f"unknown RPC error code: {code}")
    spec = ERROR_CATALOG[code]
    safe_details = redact_value(details or {})
    return RpcError(
        code=code,
        message=message or str(spec["message"]),
        user_message=user_message or str(spec["user_message"]),
        retryable=bool(spec["retryable"] if retryable is None else retryable),
        details=safe_details if isinstance(safe_details, dict) else {"summary": safe_details},
    )


def error_catalog_with_policies() -> dict[str, dict[str, Any]]:
    return {
        code: {
            **spec,
            "details_schema": "redacted object",
            "redaction_policy": "canonical_sensitive_fields_v1",
        }
        for code, spec in ERROR_CATALOG.items()
    }


def _redact_by_key(key: str, value: Any) -> Any:
    if _SENSITIVE_KEY_RE.search(str(key)):
        if value in (None, "", False):
            return value
        return "<redacted>"
    return redact_value(value)


def _redact_text(value: str) -> str:
    redacted = _SENSITIVE_TEXT_RE.sub("<redacted>", value)
    redacted = _WINDOWS_USER_PATH_RE.sub("<user-path>", redacted)
    redacted = _PRIVATE_URL_RE.sub("<private-url>", redacted)
    return redacted


def _looks_masked(value: str) -> bool:
    return "<redacted>" in value or value.startswith("***") or value.startswith("****")
