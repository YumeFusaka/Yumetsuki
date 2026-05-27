from __future__ import annotations

import threading
from time import time
from typing import Generator

from agent.executor import AgentExecutor
from agent.multi_step import MultiStepRunner
from agent.planner import AgentPlanner, AgentPlan
from agent.reflector import AgentReflector, Reflection
from config.schema import AgentConfig
from core.event_bus import event_bus
from core.log_types import LogChannel, LogLevel, build_log_event
from llm.text_processor import ProcessedText
from session.manager import SessionContextManager
from vision.types import OCRResult, VisualObservation


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
        session_manager: SessionContextManager | None = None,
        session_id: str = "default-session",
        log_service=None,
        vision_manager=None,
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
        self._session_manager = session_manager or SessionContextManager(log_service=log_service)
        self._session_id = session_id
        self._log_service = log_service
        self._vision_manager = vision_manager

    def chat_stream(
        self,
        user_input: str,
        visual_capture: OCRResult | None = None,
    ) -> Generator[ProcessedText, None, None]:
        self._record_log_event(
            channel=LogChannel.CONVERSATION,
            level=LogLevel.INFO,
            source="agent.manager",
            event_type="conversation.user_input",
            session_id=self._session_id,
            summary=f"用户输入: {user_input[:80]}",
            details={"text": user_input},
        )
        self._event_bus.publish(AgentEvents.USER_INPUT, {"text": user_input})
        session_ctx = self._session_manager.get_or_create(self._user_id, self._session_id)
        self._session_manager.record_user_input(session_ctx, user_input)
        visual_context = ""
        if visual_capture is not None:
            visual_context = self._process_visual_capture(session_ctx, visual_capture)

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
        allow_tools = True
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
            allow_tools = False
            self._event_bus.publish(AgentEvents.TOOL_EXECUTED, {
                "tool": plan.tool_name,
                "result": tool_result[:200],
            })
        else:
            self._event_bus.publish(AgentEvents.TOOL_SKIPPED, {"reason": "chat mode"})

        extra_context = self._build_extra_context(
            memories,
            tool_result,
            tool_executed=bool(tool_calls),
            visual_context=visual_context,
        )
        session_context = self._session_manager.build_prompt_context(session_ctx)

        self._event_bus.publish(AgentEvents.LLM_STARTED, {})
        final_result: ProcessedText | None = None
        assistant_response = ""
        for result in self._llm_manager.chat_stream(
            user_input,
            session_context=session_context,
            extra_context=extra_context,
            allow_tools=allow_tools,
        ):
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
        self._record_log_event(
            channel=LogChannel.CONVERSATION,
            level=LogLevel.INFO,
            source="agent.manager",
            event_type="conversation.assistant_reply",
            session_id=self._session_id,
            summary=f"角色回复: {assistant_response[:80]}",
            details={
                "text": assistant_response,
                "emotion": final_result.emotion if final_result else None,
                "tool_names": [call.get("name") for call in (tool_calls or []) if call.get("name")],
                "memory_count": len(memories),
                "character_name": "",
            },
        )
        self._session_manager.record_assistant_reply(session_ctx, assistant_response)

        # 对话结束后立即返回，记忆写入和反思均放到后台执行
        if final_result:
            self._async_persist_and_reflect(session_ctx, user_input, assistant_response, tool_calls)

    def _async_persist_and_reflect(
        self,
        session_ctx,
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
            if self._memory_store and hasattr(self._memory_store, "add_memory"):
                for candidate in self._session_manager.collect_mem0_candidates(session_ctx):
                    self._memory_store.add_memory(
                        content=candidate.content,
                        memory_type=candidate.category,
                        user_id=self._user_id,
                    )
                    if hasattr(candidate, "promoted_to_mem0"):
                        candidate.promoted_to_mem0 = True

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

    def should_capture_screen(self, user_input: str) -> bool:
        if self._vision_manager is None:
            return False
        text = user_input.strip()
        explicit_triggers = (
            "看看屏幕",
            "看一下屏幕",
            "读屏幕",
            "识别屏幕",
            "读取屏幕",
            "屏幕截图",
            "屏幕上写",
        )
        if any(trigger in text for trigger in explicit_triggers):
            return True
        has_screen_target = any(target in text for target in ("屏幕", "当前画面", "当前窗口"))
        has_read_intent = any(intent in text for intent in ("看看", "看下", "看一下", "识别", "读取", "读一下"))
        return has_screen_target and has_read_intent

    def _process_visual_capture(self, session_ctx, capture: OCRResult) -> str:
        if not capture.ok:
            return self._record_ocr_result(session_ctx, capture)
        result = self._vision_manager.recognize_image_text(capture.image_path)
        return self._record_ocr_result(session_ctx, result)

    def _record_ocr_result(self, session_ctx, result: OCRResult) -> str:
        if not result.ok or not result.text.strip():
            error = result.error or "未识别到屏幕文字"
            self._record_log_event(
                channel=LogChannel.SYSTEM,
                level=LogLevel.WARN,
                source="agent.vision",
                event_type="vision.ocr_failed",
                session_id=self._session_id,
                summary=f"OCR 未完成: {error[:80]}",
                details={"error": error, "image_path": result.image_path},
            )
            return f"视觉 OCR 未完成：{error}"

        self._session_manager.record_visual_observation(
            session_ctx,
            VisualObservation(
                text=result.text,
                source="screen_ocr",
                image_path=result.image_path,
                timestamp=time(),
            ),
        )
        self._record_log_event(
            channel=LogChannel.SYSTEM,
            level=LogLevel.INFO,
            source="agent.vision",
            event_type="vision.ocr_completed",
            session_id=self._session_id,
            summary=f"OCR 识别到 {len(result.text)} 字",
            details={"image_path": result.image_path, "text_length": len(result.text)},
            sensitive=True,
        )
        return ""

    def _should_capture_screen(self, user_input: str) -> bool:
        return self.should_capture_screen(user_input)

    def _search_memories(self, user_input: str) -> list[str]:
        if not self._memory_store:
            return []
        memories = self._memory_store.search_relevant(user_input, user_id=self._user_id)
        self._record_log_event(
            channel=LogChannel.SYSTEM,
            level=LogLevel.INFO,
            source="agent.manager",
            event_type="memory.retrieved",
            session_id=self._session_id,
            summary=f"Retrieved {len(memories)} memories",
            details={
                "count": len(memories),
                "preview": "\n".join(str(memory) for memory in memories[:3])[:200],
            },
        )
        return memories

    def set_memory_store(self, memory_store) -> None:
        self._memory_store = memory_store

    def _build_extra_context(
        self,
        memories: list[str],
        tool_result: str,
        tool_executed: bool = False,
        visual_context: str = "",
    ) -> str:
        sections: list[str] = []
        if visual_context:
            sections.append(visual_context)
        if memories:
            memory_lines = "\n".join(f"- {memory}" for memory in memories)
            sections.append(f"相关记忆:\n{memory_lines}")
        if tool_executed and tool_result:
            sections.append(
                "工具调用已成功执行。\n"
                "你刚刚已经代表用户完成了实际操作。"
                "回答时要基于下面的工具结果直接确认完成情况，"
                "不要再说自己做不到、不能操作、只能聊天。"
            )
            sections.append(f"工具结果:\n{tool_result}")
        elif tool_result:
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

    def _record_log_event(self, **kwargs) -> None:
        if self._log_service is None:
            return
        self._log_service.record(build_log_event(**kwargs))
