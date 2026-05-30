from __future__ import annotations

import pytest

from python_core.rpc.framing import FrameDecodeError, decode_frame, encode_frame


def test_encode_frame_writes_ndjson_utf8() -> None:
    frame = encode_frame({"kind": "request", "text": "你好"})
    assert frame.endswith(b"\n")
    assert decode_frame(frame)["text"] == "你好"


def test_decode_rejects_non_json_line() -> None:
    with pytest.raises(FrameDecodeError) as exc_info:
        decode_frame(b"not json\n")
    assert exc_info.value.code == "rpc.invalid_frame"


def test_decode_rejects_non_object_json() -> None:
    with pytest.raises(FrameDecodeError):
        decode_frame(b"[]\n")


def test_frame_size_limit() -> None:
    with pytest.raises(FrameDecodeError):
        encode_frame({"payload": "x" * 20}, max_bytes=10)
    with pytest.raises(FrameDecodeError):
        decode_frame(b'{"payload":"xxxxxxxxxxxxxxxxxxxx"}\n', max_bytes=10)
