from __future__ import annotations

from core.log_types import LogChannel, LogLevel, build_log_event
from session.context import SessionContext
from session.policy import SessionPolicy
from session.store import SessionContextStore
from vision.types import VisualObservation


class SessionContextManager:
    def __init__(
        self,
        store: SessionContextStore | None = None,
        policy: SessionPolicy | None = None,
        log_service=None,
    ):
        self._store = store
        self._policy = policy or SessionPolicy()
        self._log_service = log_service
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

    def record_visual_observation(self, ctx: SessionContext, observation: VisualObservation) -> None:
        ctx.visual_observations.append(observation)
        ctx.visual_observations = ctx.visual_observations[-3:]
        if self._store:
            self._store.save(ctx)

    def build_prompt_context(self, ctx: SessionContext) -> str:
        prompt_context = self._policy.build_prompt_context(ctx)
        self._record_log_event(
            channel=LogChannel.SYSTEM,
            level=LogLevel.INFO,
            source="session.manager",
            event_type="session.prompt_context_built",
            session_id=ctx.session_id,
            summary="Session prompt context built",
            details={
                "recent_turn_count": len(ctx.recent_turns),
                "working_fact_count": len(ctx.working_facts),
                "preview": prompt_context[:200],
            },
        )
        return prompt_context

    def collect_mem0_candidates(self, ctx: SessionContext):
        return self._policy.collect_mem0_candidates(ctx)

    def _record_log_event(self, **kwargs) -> None:
        if self._log_service is None:
            return
        self._log_service.record(build_log_event(**kwargs))
