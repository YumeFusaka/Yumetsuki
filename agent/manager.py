from __future__ import annotations

import threading
from typing import Generator

from agent.executor import AgentExecutor
from agent.multi_step import MultiStepRunner
from agent.planner import AgentPlanner, AgentPlan
from agent.reflector import AgentReflector, Reflection
from config.schema import AgentConfig
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
    MULTI_STEP_PROGRESS = "agent.multi_step_progress"
    USER_INPUT = "agent.user_input"
    ASSISTANT_REPLY = "agent.assistant_reply"
    THINKING = "agent.thinking"


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
        agent_config: AgentConfig | None = None,
    ):
        self._config = agent_config or AgentConfig()
        self._llm_manager = llm_manager

        # 构建 LLM helper（供 Planner/Reflector 内部使用）
        self._llm_helper = self._build_llm_helper()

        self._planner = planner or AgentPlanner(
            config=self._config.planner,
            llm_helper=self._llm_helper,
        )
        self._executor = executor or AgentExecutor()
        self._reflector = reflector or AgentReflector(
            config=self._config.reflector,
            llm_helper=self._llm_helper,
        )
        self._memory_store = memory_store
        self._tool_registry = tool_registry
        self._user_id = user_id
        self._event_bus = event_bus_instance or event_bus

    def chat_stream(self, user_input: str) -> Generator[ProcessedText, None, None]:
        self._event_bus.publish(AgentEvents.USER_INPUT, {"text": user_input})

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
        if plan.needs_multi_step and self._config.multi_step.enabled:
            # 多步推理模式
            multi_step_runner = MultiStepRunner(
                config=self._config.multi_step,
                llm_helper=self._llm_helper,
                tool_registry=self._tool_registry,
                event_bus_instance=self._event_bus,
            )
            ms_result = multi_step_runner.run(plan.goal, plan.steps, tool_entries)
            tool_result = ms_result.final_context
            tool_calls = [
                {"name": s.tool_name or "step", "result": s.tool_result}
                for s in ms_result.steps_completed
            ]
        elif plan.mode == "tool":
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
            if result.thinking:
                self._event_bus.publish(AgentEvents.THINKING, {"text": result.thinking})
            final_result = result
            assistant_response = result.clean_text
            yield result

        self._event_bus.publish(AgentEvents.LLM_COMPLETE, {
            "response_length": len(assistant_response),
        })
        self._event_bus.publish(AgentEvents.ASSISTANT_REPLY, {
            "text": assistant_response,
            "character_name": "",
        })

        # 对话结束后立即返回，记忆写入和反思均放到后台执行
        if final_result:
            self._async_persist_and_reflect(user_input, assistant_response, tool_calls)

    def _async_persist_and_reflect(
        self,
        user_input: str,
        assistant_response: str,
        tool_calls: list[dict] | None,
    ) -> None:
        """在后台线程执行记忆写入与反思，不阻塞主流程。"""
        def _run():
            if self._memory_store:
                try:
                    self._memory_store.add_conversation(
                        user_text=user_input,
                        assistant_text=assistant_response,
                        user_id=self._user_id,
                    )
                except Exception:
                    pass

            reflection = self._reflector.reflect(user_input, assistant_response, tool_calls)

            # 将提取的记忆写入 memory_store
            if reflection.memories_to_store and self._memory_store:
                for mem in reflection.memories_to_store:
                    if hasattr(self._memory_store, "add_memory"):
                        self._memory_store.add_memory(
                            content=mem.content,
                            memory_type=mem.type,
                            user_id=self._user_id,
                        )

            self._event_bus.publish(AgentEvents.REFLECTION_COMPLETE, {
                "needs_continue": reflection.needs_continue,
                "key_points": reflection.key_points,
                "memories_extracted": len(reflection.memories_to_store),
            })

        thread = threading.Thread(target=_run, daemon=True)
        thread.start()

    def _plan_to_dict(self, plan: AgentPlan) -> dict:
        return {
            "mode": plan.mode,
            "goal": plan.goal,
            "tool_name": plan.tool_name,
            "needs_multi_step": plan.needs_multi_step,
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

    def _build_llm_helper(self):
        """构建 Agent 内部 LLM helper。如果无法获取 LLM 配置则返回 None。"""
        try:
            config = self._llm_manager._config
            from agent.llm_helper import AgentLLMHelper
            return AgentLLMHelper(config)
        except (AttributeError, ImportError):
            return None
