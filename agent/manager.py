from __future__ import annotations

from typing import Generator

from agent.executor import AgentExecutor
from agent.planner import AgentPlanner
from llm.text_processor import ProcessedText


class AgentManager:
    def __init__(
        self,
        llm_manager,
        planner: AgentPlanner | None = None,
        executor: AgentExecutor | None = None,
        memory_store=None,
        tool_registry=None,
        user_id: str = "default-user",
    ):
        self._llm_manager = llm_manager
        self._planner = planner or AgentPlanner()
        self._executor = executor or AgentExecutor()
        self._memory_store = memory_store
        self._tool_registry = tool_registry
        self._user_id = user_id

    def chat_stream(self, user_input: str) -> Generator[ProcessedText, None, None]:
        memories = self._search_memories(user_input)
        tool_entries = self._tool_registry.entries() if self._tool_registry else []
        plan = self._planner.plan(user_input, tool_entries)

        tool_result = ""
        if plan.mode == "tool":
            tool_result = self._executor.execute(plan, self._tool_registry)

        extra_context = self._build_extra_context(memories, tool_result)

        final_result: ProcessedText | None = None
        for result in self._llm_manager.chat_stream(user_input, extra_context=extra_context):
            final_result = result
            yield result

        if final_result and self._memory_store:
            self._memory_store.add_conversation(
                user_text=user_input,
                assistant_text=final_result.clean_text,
                user_id=self._user_id,
            )

    def _search_memories(self, user_input: str) -> list[str]:
        if not self._memory_store:
            return []
        return self._memory_store.search_relevant(user_input, user_id=self._user_id)

    def _build_extra_context(self, memories: list[str], tool_result: str) -> str:
        sections: list[str] = []
        if memories:
            memory_lines = "\n".join(f"- {memory}" for memory in memories)
            sections.append(f"相关记忆:\n{memory_lines}")
        if tool_result:
            sections.append(f"工具结果:\n{tool_result}")
        return "\n\n".join(sections)
