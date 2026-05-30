from __future__ import annotations

import json
from typing import Any


DEFAULT_MAX_FRAME_BYTES = 256 * 1024


class FrameDecodeError(ValueError):
    code = "rpc.invalid_frame"


def encode_frame(payload: dict[str, Any], max_bytes: int = DEFAULT_MAX_FRAME_BYTES) -> bytes:
    data = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8") + b"\n"
    if len(data) > max_bytes:
        raise FrameDecodeError("frame exceeds max bytes")
    return data


def decode_frame(line: bytes, max_bytes: int = DEFAULT_MAX_FRAME_BYTES) -> dict[str, Any]:
    if len(line) > max_bytes:
        raise FrameDecodeError("frame exceeds max bytes")
    try:
        text = line.decode("utf-8")
        payload = json.loads(text)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise FrameDecodeError("invalid JSON frame") from exc
    if not isinstance(payload, dict):
        raise FrameDecodeError("frame payload must be object")
    return payload
