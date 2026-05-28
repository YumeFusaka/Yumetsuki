from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from core.log_sanitizer import sanitize_details
from core.log_types import LogChannel, LogLevel, build_log_event
from core.mcp_host import MCPHost
from core.plugin_host import PluginHost


MAX_AUDIT_TEXT_CHARS = 800
SENSITIVE_ARGUMENT_TOKENS = ("api_key", "apikey", "secret", "token", "password", "authorization", "cookie")
PATH_ARGUMENT_KEYS = {"path", "model_path", "file_path", "screenshot_path", "ref_audio_path", "log_root", "storage_dir"}
URL_ARGUMENT_KEYS = {"url", "api_url", "base_url", "endpoint"}


@dataclass(frozen=True)
class ToolEntry:
    name: str
    source: str
    qualified_name: str
    schema: dict[str, Any]
    source_name: str = ""

    def as_openai_tool(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.qualified_name,
                "description": self.schema.get("description", ""),
                "parameters": self.schema["parameters"],
            },
        }

    def parameter_summary(self) -> str:
        parameters = self.schema.get("parameters", {})
        properties = parameters.get("properties", {})
        required = set(parameters.get("required", []))
        if not properties:
            return "无参数"
        parts = []
        for name, info in properties.items():
            marker = "*" if name in required else ""
            parts.append(f"{name}{marker}:{info.get('type', 'any')}")
        return ", ".join(parts)


class ToolRegistry:
    def __init__(
        self,
        plugin_host: PluginHost | None = None,
        mcp_host: MCPHost | None = None,
        log_service=None,
    ):
        self._plugin_host = plugin_host
        self._mcp_host = mcp_host
        self._log_service = log_service
        self._entries: list[ToolEntry] = []
        self.refresh()

    def refresh(self) -> None:
        self._entries = []
        if self._plugin_host:
            for spec in self._plugin_host.tool_specs():
                function = spec["function"]
                qualified_name = function["name"]
                self._entries.append(ToolEntry(
                    name=qualified_name.split("__", 1)[-1],
                    source="plugin",
                    source_name=qualified_name.split("__", 1)[0],
                    qualified_name=qualified_name,
                    schema={
                        "description": function.get("description", ""),
                        "parameters": function["parameters"],
                    },
                ))
        if self._mcp_host:
            for spec in self._mcp_host.tool_specs():
                function = spec["function"]
                qualified_name = function["name"]
                self._entries.append(ToolEntry(
                    name=qualified_name.split("__", 1)[-1],
                    source="mcp",
                    source_name=qualified_name.split("__", 1)[0],
                    qualified_name=qualified_name,
                    schema={
                        "description": function.get("description", ""),
                        "parameters": function["parameters"],
                    },
                ))

    def tool_specs(self) -> list[dict[str, Any]]:
        return [entry.as_openai_tool() for entry in self._entries]

    def entries(self) -> list[ToolEntry]:
        return self._entries.copy()

    def counts_by_source(self) -> dict[str, int]:
        counts = {"plugin": 0, "mcp": 0}
        for entry in self._entries:
            counts[entry.source] = counts.get(entry.source, 0) + 1
        return counts

    def _record_log_event(self, **kwargs) -> None:
        if self._log_service is None:
            return
        self._log_service.record(build_log_event(**kwargs))

    def _entry_for_tool(self, qualified_name: str) -> ToolEntry | None:
        for entry in self._entries:
            if entry.qualified_name == qualified_name:
                return entry
        return None

    def _log_source_for_tool(self, qualified_name: str) -> str:
        entry = self._entry_for_tool(qualified_name)
        if entry is None:
            return "tool.registry"
        if entry.source == "plugin":
            return f"plugin.{entry.source_name}"
        if entry.source == "mcp":
            return f"mcp.{entry.source_name}"
        return "tool.registry"

    def _audit_details(
        self,
        qualified_name: str,
        arguments: dict[str, Any],
        started: float,
        result: Any = None,
        error: Exception | None = None,
    ) -> dict[str, Any]:
        entry = self._entry_for_tool(qualified_name)
        details = {
            "qualified_name": qualified_name,
            "tool_name": entry.name if entry else qualified_name,
            "source_type": entry.source if entry else "unknown",
            "source_name": entry.source_name if entry else "",
            "arguments_summary": _summarize_arguments(arguments),
            "elapsed_ms": int((time.perf_counter() - started) * 1000),
        }
        if result is not None:
            details["result_preview"] = _truncate_text(str(result))
        if error is not None:
            details["error"] = str(error)
            details["error_type"] = type(error).__name__
        return details

    def _record_tool_audit(
        self,
        qualified_name: str,
        arguments: dict[str, Any],
        started: float,
        event_type: str,
        level: LogLevel,
        session_id: str,
        utterance_id: int | None,
        result: Any = None,
        error: Exception | None = None,
    ) -> None:
        action = event_type.rsplit("_", 1)[-1]
        self._record_log_event(
            channel=LogChannel.SYSTEM,
            level=level,
            source=self._log_source_for_tool(qualified_name),
            event_type=event_type,
            session_id=session_id,
            utterance_id=utterance_id,
            summary=f"{qualified_name} {action}",
            details=self._audit_details(qualified_name, arguments, started, result=result, error=error),
            stage="tool",
        )

    def call_tool(
        self,
        qualified_name: str,
        arguments: dict[str, Any],
        session_id: str = "default-session",
        utterance_id: int | None = None,
    ) -> Any:
        started = time.perf_counter()
        self._record_tool_audit(
            qualified_name=qualified_name,
            arguments=arguments,
            started=started,
            event_type="tool.call_started",
            level=LogLevel.INFO,
            session_id=session_id,
            utterance_id=utterance_id,
        )
        if self._plugin_host:
            try:
                result = self._plugin_host.call_tool(qualified_name, arguments)
                self._record_tool_audit(
                    qualified_name=qualified_name,
                    arguments=arguments,
                    started=started,
                    event_type="tool.call_completed",
                    level=LogLevel.INFO,
                    session_id=session_id,
                    utterance_id=utterance_id,
                    result=result,
                )
                return result
            except ValueError as exc:
                entry = self._entry_for_tool(qualified_name)
                if entry is not None and entry.source == "plugin":
                    self._record_tool_audit(
                        qualified_name=qualified_name,
                        arguments=arguments,
                        started=started,
                        event_type="tool.call_failed",
                        level=LogLevel.ERROR,
                        session_id=session_id,
                        utterance_id=utterance_id,
                        error=exc,
                    )
                    raise
                pass
            except Exception as exc:
                self._record_tool_audit(
                    qualified_name=qualified_name,
                    arguments=arguments,
                    started=started,
                    event_type="tool.call_failed",
                    level=LogLevel.ERROR,
                    session_id=session_id,
                    utterance_id=utterance_id,
                    error=exc,
                )
                raise
        if self._mcp_host:
            try:
                result = self._mcp_host.call_tool(qualified_name, arguments)
                self._record_tool_audit(
                    qualified_name=qualified_name,
                    arguments=arguments,
                    started=started,
                    event_type="tool.call_completed",
                    level=LogLevel.INFO,
                    session_id=session_id,
                    utterance_id=utterance_id,
                    result=result,
                )
                return result
            except Exception as exc:
                self._record_tool_audit(
                    qualified_name=qualified_name,
                    arguments=arguments,
                    started=started,
                    event_type="tool.call_failed",
                    level=LogLevel.ERROR,
                    session_id=session_id,
                    utterance_id=utterance_id,
                    error=exc,
                )
                raise
        exc = ValueError(f"Unknown tool: {qualified_name}")
        self._record_tool_audit(
            qualified_name=qualified_name,
            arguments=arguments,
            started=started,
            event_type="tool.call_failed",
            level=LogLevel.ERROR,
            session_id=session_id,
            utterance_id=utterance_id,
            error=exc,
        )
        raise exc


def _summarize_arguments(arguments: dict[str, Any]) -> Any:
    return _summarize_value(sanitize_details(arguments))


def _summarize_value(value: Any, key_hint: str = "") -> Any:
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            normalized = str(key).lower()
            if any(token in normalized for token in SENSITIVE_ARGUMENT_TOKENS):
                result[key] = "***"
                continue
            result[key] = _summarize_value(item, normalized)
        return result
    if isinstance(value, list):
        return [_summarize_value(item, key_hint) for item in value]
    if isinstance(value, tuple):
        return [_summarize_value(item, key_hint) for item in value]
    if isinstance(value, str):
        if key_hint in URL_ARGUMENT_KEYS or _looks_like_url_with_credentials(value):
            return _mask_url_credentials(_truncate_text(value))
        if key_hint in PATH_ARGUMENT_KEYS or _looks_like_path(value):
            return _summarize_path(value)
        return _truncate_text(value)
    return value


def _truncate_text(value: str) -> str:
    if len(value) <= MAX_AUDIT_TEXT_CHARS:
        return value
    return value[:MAX_AUDIT_TEXT_CHARS] + "...<truncated>"


def _mask_url_credentials(value: str) -> str:
    try:
        parts = urlsplit(value)
    except ValueError:
        return value
    if not parts.scheme:
        return value
    netloc = parts.netloc
    if "@" in netloc:
        host = netloc.split("@", 1)[1]
        netloc = f"***@{host}"
    return urlunsplit((parts.scheme, netloc, parts.path, _mask_url_query(parts.query), parts.fragment))


def _mask_url_query(query: str) -> str:
    if not query:
        return query
    masked_parts = []
    for part in query.split("&"):
        key, separator, value = part.partition("=")
        if separator and any(token in key.lower() for token in SENSITIVE_ARGUMENT_TOKENS):
            masked_parts.append(f"{key}=***")
            continue
        masked_parts.append(part)
    return "&".join(masked_parts)


def _looks_like_url_with_credentials(value: str) -> bool:
    try:
        parts = urlsplit(value)
    except ValueError:
        return False
    return bool(parts.scheme and "@" in parts.netloc)


def _summarize_path(value: str) -> str:
    normalized = value.replace("\\", "/").rstrip("/")
    if not normalized:
        return value
    name = normalized.rsplit("/", 1)[-1]
    if not name or name == normalized:
        return _truncate_text(value)
    return f"***/{name}"


def _looks_like_path(value: str) -> bool:
    if len(value) > 260:
        return False
    try:
        parts = urlsplit(value)
    except ValueError:
        parts = None
    if parts is not None and parts.scheme and parts.netloc:
        return False
    normalized = value.replace("\\", "/")
    return (
        ":/" in normalized
        or normalized.startswith("/")
        or normalized.startswith("~/")
        or normalized.count("/") >= 2
    )
