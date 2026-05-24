from __future__ import annotations

from session.context import SessionContext
from session.policy import SessionPolicy
from session.store import SessionContextStore


class SessionContextManager:
    def __init__(
        self,
        store: SessionContextStore | None = None,
        policy: SessionPolicy | None = None,
    ):
        self._store = store
        self._policy = policy or SessionPolicy()
        self._live: dict[tuple[str, str], SessionContext] = {}

    def get_or_create(self, user_id: str, session_id: str) -> SessionContext:
        key = (user_id, session_id)
        if key in self._live:
            return self._live[key]
        ctx = self._store.load(user_id, session_id) if self._store else None
        if ctx is None:
            ctx = SessionContext.new(session_id=session_id, user_id=user_id)
        self._live[key] = ctx
        return ctx

    def record_user_input(self, ctx: SessionContext, text: str) -> None:
        self._policy.record_user_input(ctx, text)

    def record_assistant_reply(self, ctx: SessionContext, text: str) -> None:
        self._policy.record_assistant_reply(ctx, text)
        if self._store:
            self._store.save(ctx)

    def build_prompt_context(self, ctx: SessionContext) -> str:
        return self._policy.build_prompt_context(ctx)

    def collect_mem0_candidates(self, ctx: SessionContext):
        return self._policy.collect_mem0_candidates(ctx)
