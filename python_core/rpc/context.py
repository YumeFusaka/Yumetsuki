from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RpcContext:
    request_id: str
    trace_id: str
    parent_trace_id: str | None
    session_id: str
    protocol_version: int
