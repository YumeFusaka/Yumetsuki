from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Generator

from config.schema import MultiStepConfig
from core.event_bus import event_bus

logger = logging.getLogger(__name__)


@dataclass
class StepResult:
    step_index: int
    description: str
    tool_name: str | None = None
    tool_result: str = ""
    success: bool = True


@dataclass
class MultiStepResult:
    steps_completed: list[StepResult] = field(default_factory=list)
    final_context: str = ""
    timed_out: bool = False
    max_steps_reached: bool = False


# LLM 规划下一步的 prompt
_PLAN_NEXT_STEP_PROMPT = """你是一个任务规划器。根据用户目标和已完成的步骤，决定下一步操作。
输出严格 JSON：
{"action": "tool"|"done", "tool_name": "工具名或null", "arguments": {}, "description": "这一步做什么"}

规则：
- 如果目标已完成，action=done
- 如果需要调用工具，action=tool，指定 tool_name 和 arguments
- 每次只输出一步"""


class MultiStepRunner:
    """多步推理引擎。Plan → Execute → Observe 循环。"""

    MULTI_STEP_PROGRESS = "agent.multi_step_progress"

    def __init__(
        self,
        config: MultiStepConfig | None = None,
        llm_helper=None,
        tool_registry=None,
        event_bus_instance=None,
    ):
        self._config = config or MultiStepConfig()
        self._llm = llm_helper
        self._tool_registry = tool_registry
        self._event_bus = event_bus_instance or event_bus

    def run(self, goal: str, initial_steps: list[str], tools: list) -> MultiStepResult:
        """执行多步推理循环。"""
        result = MultiStepResult()
        start_time = time.time()

        for step_idx in range(self._config.max_steps):
            # 检查总超时
            elapsed = time.time() - start_time
            if elapsed > self._config.total_timeout:
                result.timed_out = True
                logger.warning(f"Multi-step timed out after {elapsed:.1f}s")
                break

            # 规划下一步
            next_step = self._plan_next_step(goal, initial_steps, result.steps_completed, tools)
            if next_step is None or next_step.get("action") == "done":
                break

            # 执行
            step_result = self._execute_step(step_idx, next_step)
            result.steps_completed.append(step_result)

            # 发布进度事件
            self._event_bus.publish(self.MULTI_STEP_PROGRESS, {
                "step_index": step_idx,
                "total_steps": len(initial_steps),
                "description": step_result.description,
                "success": step_result.success,
            })

            if not step_result.success:
                logger.warning(f"Step {step_idx} failed: {step_result.description}")
                # 失败不中断，继续下一步
                continue
        else:
            # 循环正常结束（达到最大步数）
            result.max_steps_reached = True

        # 构建最终上下文
        result.final_context = self._build_final_context(goal, result.steps_completed)
        return result

    def _plan_next_step(
        self,
        goal: str,
        initial_steps: list[str],
        completed: list[StepResult],
        tools: list,
    ) -> dict | None:
        """调用 LLM 规划下一步。"""
        if not self._llm:
            # 无 LLM 时按 initial_steps 顺序执行
            if len(completed) < len(initial_steps):
                return {
                    "action": "tool",
                    "tool_name": None,
                    "arguments": {},
                    "description": initial_steps[len(completed)],
                }
            return {"action": "done"}

        tool_desc = "\n".join(
            f"- {t.qualified_name}: {t.schema.get('description', '')}"
            for t in tools
        ) or "无可用工具"

        completed_desc = "\n".join(
            f"  步骤{s.step_index + 1}: {s.description} → {'成功' if s.success else '失败'}: {s.tool_result[:100]}"
            for s in completed
        ) or "  无"

        user_prompt = (
            f"目标: {goal}\n"
            f"计划步骤: {', '.join(initial_steps)}\n"
            f"已完成:\n{completed_desc}\n"
            f"可用工具:\n{tool_desc}\n"
            f"请规划下一步。"
        )

        return self._llm.judge_json(
            _PLAN_NEXT_STEP_PROMPT,
            user_prompt,
            max_tokens=200,
        ) or {"action": "done"}

    def _execute_step(self, step_idx: int, step_plan: dict) -> StepResult:
        """执行单步操作。"""
        tool_name = step_plan.get("tool_name")
        arguments = step_plan.get("arguments", {})
        description = step_plan.get("description", f"步骤 {step_idx + 1}")

        if not tool_name or not self._tool_registry:
            return StepResult(
                step_index=step_idx,
                description=description,
                tool_name=tool_name,
                tool_result="",
                success=True,
            )

        try:
            start = time.time()
            result = self._tool_registry.call_tool(tool_name, arguments)
            elapsed = time.time() - start

            if elapsed > self._config.step_timeout:
                return StepResult(
                    step_index=step_idx,
                    description=description,
                    tool_name=tool_name,
                    tool_result=f"超时 ({elapsed:.1f}s)",
                    success=False,
                )

            return StepResult(
                step_index=step_idx,
                description=description,
                tool_name=tool_name,
                tool_result=str(result)[:500],
                success=True,
            )
        except Exception as exc:
            return StepResult(
                step_index=step_idx,
                description=description,
                tool_name=tool_name,
                tool_result=f"错误: {exc}",
                success=False,
            )

    def _build_final_context(self, goal: str, steps: list[StepResult]) -> str:
        """将多步结果汇总为上下文字符串。"""
        if not steps:
            return ""
        lines = [f"多步推理完成 (目标: {goal}):"]
        for s in steps:
            status = "✓" if s.success else "✗"
            line = f"  {status} {s.description}"
            if s.tool_result:
                line += f" → {s.tool_result[:200]}"
            lines.append(line)
        return "\n".join(lines)
