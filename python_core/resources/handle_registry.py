from __future__ import annotations

import json
import os
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class ResourceHandle:
    handle_id: str
    kind: str
    owner_request_id: str
    expires_at: float
    path: Path | None = None
    content: bytes | str | dict[str, Any] | list[Any] | None = None


class HandleRegistry:
    def __init__(self, temp_root: Path, ttl_seconds: float = 300.0) -> None:
        self.temp_root = temp_root.resolve()
        self.temp_root.mkdir(parents=True, exist_ok=True)
        self.ttl_seconds = ttl_seconds
        self._handles: dict[str, ResourceHandle] = {}

    def create_text(self, owner_request_id: str, text: str, ttl_seconds: float | None = None) -> str:
        return self._store("text", owner_request_id, text, ttl_seconds)

    def create_json(self, owner_request_id: str, payload: dict[str, Any] | list[Any], ttl_seconds: float | None = None) -> str:
        return self._store("json", owner_request_id, payload, ttl_seconds)

    def create_bytes(self, owner_request_id: str, kind: str, payload: bytes, ttl_seconds: float | None = None) -> str:
        if kind not in {"audio", "image", "file"}:
            raise ValueError("invalid handle kind")
        handle_id = self._new_handle_id()
        path = (self.temp_root / f"{handle_id}.bin").resolve()
        self._assert_in_scope(path)
        path.write_bytes(payload)
        self._handles[handle_id] = ResourceHandle(handle_id, kind, owner_request_id, self._expires(ttl_seconds), path=path)
        return handle_id

    def stat(self, owner_request_id: str, handle_id: str) -> dict[str, Any]:
        handle = self._get(owner_request_id, handle_id)
        return {
            "handle_id": handle.handle_id,
            "kind": handle.kind,
            "byte_length": len(self._bytes(handle)),
            "expires_at_ms": int(handle.expires_at * 1000),
        }

    def read_range(self, owner_request_id: str, handle_id: str, start: int, length: int) -> bytes:
        data = self._bytes(self._get(owner_request_id, handle_id))
        return data[start : start + length]

    def read_page(self, owner_request_id: str, handle_id: str, page_token: str | None = None, limit: int = 100) -> dict[str, Any]:
        data = self._bytes(self._get(owner_request_id, handle_id)).decode("utf-8")
        start = int(page_token or 0)
        end = min(start + limit, len(data))
        return {"text": data[start:end], "next_token": str(end) if end < len(data) else None}

    def release(self, owner_request_id: str, handle_id: str) -> bool:
        handle = self._handles.get(handle_id)
        if handle is None:
            return False
        if handle.owner_request_id != owner_request_id:
            raise PermissionError("handle owner mismatch")
        self._delete(handle)
        self._handles.pop(handle_id, None)
        return True

    def cleanup_owner(self, owner_request_id: str) -> None:
        for handle_id, handle in list(self._handles.items()):
            if handle.owner_request_id == owner_request_id:
                self._delete(handle)
                self._handles.pop(handle_id, None)

    def cleanup_expired(self) -> None:
        now = time.time()
        for handle_id, handle in list(self._handles.items()):
            if now > handle.expires_at:
                self._delete(handle)
                self._handles.pop(handle_id, None)

    def shutdown(self) -> None:
        for handle in list(self._handles.values()):
            self._delete(handle)
        self._handles.clear()

    def _store(self, kind: str, owner_request_id: str, content: Any, ttl_seconds: float | None) -> str:
        handle_id = self._new_handle_id()
        self._handles[handle_id] = ResourceHandle(handle_id, kind, owner_request_id, self._expires(ttl_seconds), content=content)
        return handle_id

    def _get(self, owner_request_id: str, handle_id: str) -> ResourceHandle:
        handle = self._handles.get(handle_id)
        if handle is None:
            raise KeyError("filesystem.handle_expired")
        if time.time() > handle.expires_at:
            self._delete(handle)
            self._handles.pop(handle_id, None)
            raise KeyError("filesystem.handle_expired")
        if handle.owner_request_id != owner_request_id:
            raise PermissionError("handle owner mismatch")
        return handle

    def _bytes(self, handle: ResourceHandle) -> bytes:
        if handle.path is not None:
            return handle.path.read_bytes()
        if isinstance(handle.content, bytes):
            return handle.content
        if isinstance(handle.content, str):
            return handle.content.encode("utf-8")
        return json.dumps(handle.content, ensure_ascii=False).encode("utf-8")

    def _new_handle_id(self) -> str:
        return "h_" + uuid.uuid4().hex

    def _expires(self, ttl_seconds: float | None) -> float:
        return time.time() + (self.ttl_seconds if ttl_seconds is None else ttl_seconds)

    def _assert_in_scope(self, path: Path) -> None:
        try:
            path.relative_to(self.temp_root)
        except ValueError as exc:
            raise ValueError("filesystem.path_out_of_scope") from exc

    def _delete(self, handle: ResourceHandle) -> None:
        if handle.path is not None:
            try:
                os.remove(handle.path)
            except FileNotFoundError:
                pass
