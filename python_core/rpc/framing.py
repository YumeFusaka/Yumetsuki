from __future__ import annotations

import json
import sys
from typing import Any, BinaryIO

from .errors import RpcError, make_error


DEFAULT_MAX_FRAME_BYTES = 256 * 1024


class RpcFrameError(ValueError):
    def __init__(self, rpc_error: RpcError):
        super().__init__(rpc_error.message)
        self.rpc_error = rpc_error


def encode_frame(payload: dict[str, Any], max_bytes: int = DEFAULT_MAX_FRAME_BYTES) -> bytes:
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
    frame = encoded + b"\n"
    if len(frame) > max_bytes:
        raise RpcFrameError(
            make_error(
                "rpc.invalid_frame",
                message="RPC frame exceeds maximum size.",
                details={"frame_bytes": len(frame), "max_bytes": max_bytes},
            )
        )
    return frame


def decode_frame(line: bytes, max_bytes: int = DEFAULT_MAX_FRAME_BYTES) -> dict[str, Any]:
    if len(line) > max_bytes:
        raise RpcFrameError(
            make_error(
                "rpc.invalid_frame",
                message="RPC frame exceeds maximum size.",
                details={"frame_bytes": len(line), "max_bytes": max_bytes},
            )
        )
    try:
        decoded = json.loads(line.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RpcFrameError(make_error("rpc.invalid_frame", details={"summary": str(exc)})) from exc
    if not isinstance(decoded, dict):
        raise RpcFrameError(make_error("rpc.invalid_frame", details={"summary": "frame root is not object"}))
    return decoded


class ProtocolWriter:
    """The only sidecar helper allowed to write protocol frames to stdout."""

    def __init__(self, stream: BinaryIO | None = None, max_bytes: int = DEFAULT_MAX_FRAME_BYTES):
        self._stream = stream if stream is not None else sys.stdout.buffer
        self._max_bytes = max_bytes

    def write(self, payload: dict[str, Any]) -> None:
        self._stream.write(encode_frame(payload, max_bytes=self._max_bytes))
        self._stream.flush()
