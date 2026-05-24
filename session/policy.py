from __future__ import annotations

import uuid

from config.schema import AgentConfig, SessionContextConfig
from session.context import SessionContext, SessionTurn, WorkingFact


class SessionPolicy:
    def __init__(self, config: SessionContextConfig | None = None):
        self._config = config or AgentConfig().session_context

    def record_user_input(self, ctx: SessionContext, text: str) -> None:
        turn_id = ctx.turn_counter + 1
        ctx.append_turn(SessionTurn.user(turn_id=turn_id, text=text))
        self._trim_recent_turns(ctx)
        if "先不要" in text or "只讨论" in text:
            ctx.working_facts.append(
                WorkingFact(
                    fact_id=uuid.uuid4().hex,
                    content=text,
                    category="constraint",
                    importance=0.95,
                    created_turn_id=turn_id,
                    last_seen_turn_id=turn_id,
                    ttl_turns=self._config.constraint_ttl_turns,
                    source="user",
                    sticky=True,
                )
            )
            self._trim_working_facts(ctx)
        if "记住" in text:
            ctx.working_facts.append(
                WorkingFact(
                    fact_id=uuid.uuid4().hex,
                    content=text,
                    category="preference",
                    importance=0.95,
                    created_turn_id=turn_id,
                    last_seen_turn_id=turn_id,
                    ttl_turns=self._config.constraint_ttl_turns,
                    source="user",
                    sticky=True,
                )
            )
            self._trim_working_facts(ctx)
        if not ctx.summary.current_topic:
            ctx.summary.current_topic = text[:32]
            ctx.summary.updated_turn_id = turn_id

    def record_assistant_reply(self, ctx: SessionContext, text: str) -> None:
        turn_id = ctx.turn_counter + 1
        ctx.append_turn(SessionTurn.assistant(turn_id=turn_id, text=text))
        self._trim_recent_turns(ctx)

    def build_prompt_context(self, ctx: SessionContext) -> str:
        lines = ["当前会话短期上下文:"]
        lines.append(f"- 当前主题: {ctx.summary.current_topic}")
        if ctx.working_facts:
            lines.append("- 最近高优先级信息:")
            for fact in ctx.working_facts[-self._config.prompt_facts_limit:]:
                lines.append(f"  - {fact.content}")
        if ctx.recent_turns:
            lines.append("- 最近对话:")
            for turn in ctx.recent_turns[-self._config.prompt_turns_limit:]:
                lines.append(f"  - {turn.role}: {turn.text}")
        return "\n".join(lines)

    def collect_mem0_candidates(self, ctx: SessionContext) -> list[WorkingFact]:
        return [
            fact
            for fact in ctx.working_facts
            if fact.importance >= self._config.mem0_promotion_importance
            and fact.category in {"constraint", "preference", "intent"}
            and not fact.promoted_to_mem0
        ]

    def _trim_recent_turns(self, ctx: SessionContext) -> None:
        limit = self._config.recent_turns_limit
        if limit > 0 and len(ctx.recent_turns) > limit:
            ctx.recent_turns = ctx.recent_turns[-limit:]

    def _trim_working_facts(self, ctx: SessionContext) -> None:
        limit = self._config.working_facts_limit
        if limit > 0 and len(ctx.working_facts) > limit:
            ctx.working_facts = ctx.working_facts[-limit:]
