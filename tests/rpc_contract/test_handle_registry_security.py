from __future__ import annotations

import pytest

from python_core.resources import HandleRegistry


def test_cross_owner_read_is_rejected(tmp_path) -> None:
    registry = HandleRegistry(tmp_path)
    handle = registry.create_text("req1", "secret")
    with pytest.raises(PermissionError):
        registry.read_range("req2", handle, 0, 1)


def test_file_handle_does_not_expose_path_or_filename(tmp_path) -> None:
    registry = HandleRegistry(tmp_path)
    handle = registry.create_bytes("req", "file", b"data")
    assert str(tmp_path) not in handle
    assert "data" not in handle
    stat = registry.stat("req", handle)
    assert "path" not in stat


def test_temp_file_deleted_on_release_and_shutdown(tmp_path) -> None:
    registry = HandleRegistry(tmp_path)
    handle = registry.create_bytes("req", "file", b"data")
    paths = [item.path for item in registry._handles.values()]
    assert paths[0].exists()
    registry.release("req", handle)
    assert not paths[0].exists()

    other = registry.create_bytes("req", "file", b"data")
    other_path = next(iter(registry._handles.values())).path
    registry.shutdown()
    assert not other_path.exists()
    assert registry.release("req", other) is False
