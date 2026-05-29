from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RpcContext:
    request_id: str
    trace_id: str
    parent_trace_id: str | None
    session_id: str
    deadline_ms: int
    user_id: str | None = None
    stage: str = "rpc"
    cancel_token: object | None = None
