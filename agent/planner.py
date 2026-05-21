from __future__ import annotations

import re
from dataclasses import dataclass, field

from config.schema import PlannerConfig
from core.tool_registry import ToolEntry


@dataclass(frozen=True)
class AgentPlan:
    mode: str  # "chat" | "tool" | "multi_step"
    goal: str
    tool_name: str | None = None
    arguments: dict[str, object] = field(default_factory=dict)
    needs_multi_step: bool = False
    steps: list[str] = field(default_factory=list)


# LLM 精判 system prompt
_JUDGE_SYSTEM_PROMPT = """你是一个意图分类器。根据用户输入和可用工具列表，判断用户意图。
输出严格 JSON，不要输出其他内容：
{"mode": "chat"|"tool"|"multi_step", "goal": "简短描述", "tool_name": "工具名或null", "needs_multi_step": true|false, "steps": ["步骤1", "步骤2"]}

规则：
- 普通对话/闲聊/问候 → mode=chat
- 明确需要调用某个工具 → mode=tool, tool_name=工具qualified_name
- 需要多步操作（先做A再做B）→ mode=multi_step, needs_multi_step=true, steps列出每步
- 如果不确定，选 chat"""

# 多动作模式关键词
_MULTI_ACTION_PATTERNS = (
    "先", "然后", "再", "接着", "之后",
    "并且", "同时", "顺便",
    "帮我.*然后", "帮我.*再",
)


class AgentPlanner:
    _TOOL_INTENT_KEYWORDS = (
        "搜索", "查", "查找", "找一下", "帮我", "执行",
        "find", "search", "lookup",
    )

    def __init__(
        self,
        config: PlannerConfig | None = None,
        llm_helper=None,
    ):
        self._config = config or PlannerConfig()
        self._llm = llm_helper

    def plan(self, user_input: str, tools: list[ToolEntry]) -> AgentPlan:
        """分层路由：快速路由 → 按需 LLM 精判。"""
        fast_result = self._fast_route(user_input, tools)

        # 如果 LLM 精判未启用或无 LLM helper，直接返回快速路由结果
        if not self._config.llm_judge_enabled or self._llm is None:
            return fast_result

        # 判断是否需要升级到 LLM 精判
        if not self._should_escalate(user_input, fast_result):
            return fast_result

        # LLM 精判
        judge_result = self._llm_judge(user_input, tools)
        if judge_result is not None:
            return judge_result

        # 精判失败，降级为快速路由结果
        return fast_result

    def _fast_route(self, user_input: str, tools: list[ToolEntry]) -> AgentPlan:
        """关键词匹配快速路由（零开销）。"""
        normalized = user_input.lower()
        if not self._looks_like_tool_request(normalized):
            return AgentPlan(mode="chat", goal="reply")

        for tool in tools:
            if self._matches_tool(normalized, tool):
                return AgentPlan(
                    mode="tool",
                    goal=f"use {tool.qualified_name}",
                    tool_name=tool.qualified_name,
                    arguments={"query": user_input},
                )

        return AgentPlan(mode="chat", goal="reply")

    def _should_escalate(self, user_input: str, fast_result: AgentPlan) -> bool:
        """判断是否需要 LLM 精判。"""
        # 快速路由命中工具 → 需要精判确认
        if fast_result.mode == "tool":
            return True

        # 输入超过复杂度阈值
        if len(user_input) > self._config.complexity_threshold:
            return True

        # 多动作模式
        if self._has_multi_action_pattern(user_input):
            return True

        # 自定义触发关键词
        normalized = user_input.lower()
        for kw in self._config.extra_trigger_keywords:
            if kw.lower() in normalized:
                return True

        return False

    def _has_multi_action_pattern(self, user_input: str) -> bool:
        """检测多动作模式。"""
        for pattern in _MULTI_ACTION_PATTERNS:
            if re.search(pattern, user_input):
                return True
        return False

    def _llm_judge(self, user_input: str, tools: list[ToolEntry]) -> AgentPlan | None:
        """调用 LLM 做意图精判。失败返回 None。"""
        tool_desc = "\n".join(
            f"- {t.qualified_name}: {t.schema.get('description', '')}"
            for t in tools
        ) or "无可用工具"

        user_prompt = f"可用工具:\n{tool_desc}\n\n用户输入: {user_input}"

        result = self._llm.judge_json(
            _JUDGE_SYSTEM_PROMPT,
            user_prompt,
            max_tokens=self._config.judge_max_tokens,
        )

        if not result or "mode" not in result:
            return None

        mode = result.get("mode", "chat")
        if mode not in ("chat", "tool", "multi_step"):
            mode = "chat"

        tool_name = result.get("tool_name")
        # 验证工具名存在
        if mode == "tool" and tool_name:
            valid_names = {t.qualified_name for t in tools}
            if tool_name not in valid_names:
                tool_name = None
                mode = "chat"

        needs_multi_step = result.get("needs_multi_step", False)
        steps = result.get("steps", []) or []

        if mode == "multi_step":
            needs_multi_step = True

        return AgentPlan(
            mode=mode,
            goal=result.get("goal", ""),
            tool_name=tool_name,
            arguments={"query": user_input} if tool_name else {},
            needs_multi_step=needs_multi_step,
            steps=steps,
        )

    def _looks_like_tool_request(self, normalized_input: str) -> bool:
        return any(keyword in normalized_input for keyword in self._TOOL_INTENT_KEYWORDS)

    def _matches_tool(self, normalized_input: str, tool: ToolEntry) -> bool:
        haystacks = [
            tool.qualified_name.lower(),
            tool.name.lower(),
            str(tool.schema.get("description", "")).lower(),
        ]
        return any(
            any(token and token in normalized_input for token in self._tokenize(text))
            for text in haystacks
        )

    def _tokenize(self, text: str) -> list[str]:
        normalized = text.replace("__", " ").replace("_", " ").replace("-", " ")
        tokens: list[str] = []
        for part in re.findall(r"[一-鿿]{2,}|[a-zA-Z0-9]+", normalized):
            tokens.append(part)
            if re.fullmatch(r"[一-鿿]{2,}", part):
                tokens.extend(self._cn_ngrams(part))
        return list(dict.fromkeys(token for token in tokens if len(token) >= 2))

    def _cn_ngrams(self, text: str) -> list[str]:
        grams: list[str] = []
        for size in range(2, min(5, len(text) + 1)):
            for index in range(0, len(text) - size + 1):
                grams.append(text[index:index + size])
        return grams
