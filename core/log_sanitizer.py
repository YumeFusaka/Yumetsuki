from __future__ import annotations

from pathlib import PurePath, PureWindowsPath
from urllib.parse import urlsplit, urlunsplit


SENSITIVE_KEYS = {"api_key", "token", "password", "authorization", "cookie", "secret"}
SENSITIVE_KEY_PARTS = ("api_key", "token", "password", "authorization", "cookie", "secret")
URL_KEYS = {"api_url", "base_url", "url"}
PATH_KEYS = {"model_path", "screenshot_path", "ref_audio_path", "log_root", "storage_dir"}
PATH_KEY_PARTS = ("path", "root", "dir")
LONG_TEXT_KEYS = {"ocr_text", "page_text", "prompt_text", "text"}
MAX_TEXT_CHARS = 800


def _is_sensitive_key(key: str) -> bool:
    normalized = key.lower()
    return normalized in SENSITIVE_KEYS or any(part in normalized for part in SENSITIVE_KEY_PARTS)


def _is_path_key(key: str) -> bool:
    normalized = key.lower()
    return normalized in PATH_KEYS or any(part in normalized for part in PATH_KEY_PARTS)


def _mask_url(value: str) -> str:
    try:
        parts = urlsplit(value)
    except ValueError:
        return value
    if not parts.scheme or not parts.netloc or "@" not in parts.netloc:
        return value
    host = parts.netloc.split("@", 1)[1]
    return urlunsplit((parts.scheme, f"***@{host}", parts.path, parts.query, parts.fragment))


def _summarize_path(value: str) -> str:
    if not value:
        return value
    path = PureWindowsPath(value) if "\\" in value or ":" in value else PurePath(value)
    name = path.name
    if not name or name == value:
        return value
    return f"***/{name}"


def _truncate_text(value: str) -> str:
    if len(value) <= MAX_TEXT_CHARS:
        return value
    return value[:MAX_TEXT_CHARS] + "...<truncated>"


def sanitize_details(value, key_hint: str = ""):
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            normalized = key.lower()
            if _is_sensitive_key(normalized):
                result[key] = "***"
                continue
            result[key] = sanitize_details(item, normalized)
        return result
    if isinstance(value, list):
        return [sanitize_details(item, key_hint) for item in value]
    if isinstance(value, str):
        if key_hint in URL_KEYS:
            return _mask_url(value)
        if _is_path_key(key_hint):
            return _summarize_path(value)
        if key_hint in LONG_TEXT_KEYS:
            return _truncate_text(value)
        return _mask_url(value)
    return value
