from __future__ import annotations

import pytest

from python_core.rpc.framing import RpcFrameError, decode_frame, encode_frame


def test_ndjson_frame_round_trip() -> None:
    payload = {"kind": "request", "request_id": "req_1", "params": {"text": "你好"}}
    frame = encode_frame(payload)
    assert frame.endswith(b"\n")
    assert decode_frame(frame) == payload


def test_invalid_json_line_maps_to_rpc_frame_error() -> None:
    with pytest.raises(RpcFrameError) as exc:
        decode_frame(b"not-json\n")
    assert exc.value.rpc_error.code == "rpc.invalid_frame"


def test_frame_size_limit_is_enforced() -> None:
    with pytest.raises(RpcFrameError) as exc:
        encode_frame({"value": "x" * 20}, max_bytes=10)
    assert exc.value.rpc_error.code == "rpc.invalid_frame"
