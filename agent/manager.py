from __future__ import annotations

from typing import Generator

from agent.executor import AgentExecutor
from agent.planner import AgentPlanner, AgentPlan
from agent.reflector import AgentReflector, Reflection
from core.event_bus import event_bus
from llm.text_processor import ProcessedText


class AgentEvents:
    PLANNER_DECIDED = "agent.planner_decided"
    MEMORY_RETRIEVED = "agent.memory_retrieved"
    TOOL_EXECUTED = "agent.tool_executed"
    TOOL_SKIPPED = "agent.tool_skipped"
    REFLECTION_COMPLETE = "agent.reflection_complete"
    LLM_STARTED = "agent.llm_started"
    LLM_COMPLETE = "agent.llm_complete"


class AgentManager:
    def __init__(
        self,
        llm_manager,
        planner: AgentPlanner | None = None,
        executor: AgentExecutor | None = None,
        reflector: AgentReflector | None = None,
        memory_store=None,
        tool_registry=None,
        user_id: str = "default-user",
        event_bus_instance=None,
    ):
        self._llm_manager = llm_manager
        self._planner = planner or AgentPlanner()
        self._executor = executor or AgentExecutor()
        self._reflector = reflector or AgentReflector()
        self._memory_store = memory_store
        self._tool_registry = tool_registry
        self._user_id = user_id
        self._event_bus = event_bus_instance or event_bus

    def chat_stream(self, user_input: str) -> Generator[ProcessedText, None, None]:
        memories = self._search_memories(user_input)
        if memories:
            self._event_bus.publish(AgentEvents.MEMORY_RETRIEVED, {
                "count": len(memories),
                "memories": memories,
            })

        tool_entries = self._tool_registry.entries() if self._tool_registry else []
        plan = self._planner.plan(user_input, tool_entries)
        self._event_bus.publish(AgentEvents.PLANNER_DECIDED, self._plan_to_dict(plan))

        tool_result = ""
        tool_calls: list[dict] | None = None
        if plan.mode == "tool":
            result = self._executor.execute(plan, self._tool_registry)
            tool_result = str(result)
            tool_calls = [{"name": plan.tool_name, "result": tool_result}]
            self._event_bus.publish(AgentEvents.TOOL_EXECUTED, {
                "tool": plan.tool_name,
                "result": tool_result[:200],
            })
        else:
            self._event_bus.publish(AgentEvents.TOOL_SKIPPED, {"reason": "chat mode"})

        extra_context = self._build_extra_context(memories, tool_result)

        self._event_bus.publish(AgentEvents.LLM_STARTED, {})
        final_result: ProcessedText | None = None
        assistant_response = ""
        for result in self._llm_manager.chat_stream(user_input, extra_context=extra_context):
            final_result = result
            assistant_response = result.clean_text
            yield result

        self._event_bus.publish(AgentEvents.LLM_COMPLETE, {
            "response_length": len(assistant_response),
        })

        if final_result and self._memory_store:
            self._memory_store.add_conversation(
                user_text=user_input,
                assistant_text=final_result.clean_text,
                user_id=self._user_id,
            )
            reflection = self._reflector.reflect(user_input, assistant_response, tool_calls)
            self._event_bus.publish(AgentEvents.REFLECTION_COMPLETE, {
                "needs_continue": reflection.needs_continue,
                "key_points": reflection.key_points,
            })

    def _plan_to_dict(self, plan: AgentPlan) -> dict:
        return {
            "mode": plan.mode,
            "goal": plan.goal,
            "tool_name": plan.tool_name,
        }

    def _search_memories(self, user_input: str) -> list[str]:
        if not self._memory_store:
            return []
        return self._memory_store.search_relevant(user_input, user_id=self._user_id)

    def set_memory_store(self, memory_store) -> None:
        self._memory_store = memory_store

    def _build_extra_context(self, memories: list[str], tool_result: str) -> str:
        sections: list[str] = []
        if memories:
            memory_lines = "\n".join(f"- {memory}" for memory in memories)
            sections.append(f"相关记忆:\n{memory_lines}")
        if tool_result:
            sections.append(f"工具结果:\n{tool_result}")
        return "\n\n".join(sections)
