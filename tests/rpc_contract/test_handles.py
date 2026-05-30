from __future__ import annotations

import time

import pytest

from python_core.resources import HandleRegistry


def test_create_and_read_text_json_and_bytes_handles(tmp_path) -> None:
    registry = HandleRegistry(tmp_path)
    text = registry.create_text("req", "hello world")
    data = registry.create_json("req", {"a": 1})
    audio = registry.create_bytes("req", "audio", b"abcdef")

    assert registry.read_range("req", text, 0, 5) == b"hello"
    assert registry.read_page("req", data, limit=20)["text"] == '{"a": 1}'
    assert registry.stat("req", audio)["kind"] == "audio"
    assert registry.release("req", audio) is True
    assert registry.release("req", audio) is False


def test_handle_ttl_expiry(tmp_path) -> None:
    registry = HandleRegistry(tmp_path, ttl_seconds=0.01)
    handle = registry.create_text("req", "hello")
    time.sleep(0.02)
    with pytest.raises(KeyError, match="filesystem.handle_expired"):
        registry.stat("req", handle)


def test_cleanup_owner_and_shutdown(tmp_path) -> None:
    registry = HandleRegistry(tmp_path)
    first = registry.create_text("req1", "a")
    second = registry.create_text("req2", "b")
    registry.cleanup_owner("req1")
    with pytest.raises(KeyError):
        registry.stat("req1", first)
    assert registry.stat("req2", second)["kind"] == "text"
    registry.shutdown()
    with pytest.raises(KeyError):
        registry.stat("req2", second)
