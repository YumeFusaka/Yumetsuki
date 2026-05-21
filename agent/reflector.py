from __future__ import annotations

import logging
from dataclasses import dataclass, field

from config.schema import ReflectorConfig

logger = logging.getLogger(__name__)


@dataclass
class MemoryEntry:
    type: str  # "preference" | "fact" | "emotion" | "topic"
    content: str
    confidence: float = 0.8


@dataclass
class Reflection:
    needs_continue: bool
    summary: str
    key_points: list[str]
    memories_to_store: list[MemoryEntry] = field(default_factory=list)


# LLM 深度反思 prompt
_REFLECT_SYSTEM_PROMPT = """你是一个对话分析器。分析以下对话，提取值得长期记住的信息。
输出严格 JSON，不要输出其他内容：
{"memories": [{"type": "preference|fact|emotion|topic", "content": "具体内容", "confidence": 0.0-1.0}], "key_points": ["要点1", "要点2"]}

提取规则：
- preference: 用户表达的喜好（"我喜欢..."、"我不喜欢..."、"我偏好..."）
- fact: 用户的事实信息（"我住在..."、"我的工作是..."、"我叫..."）
- emotion: 用户当前情绪状态
- topic: 对话主题标签
- confidence: 你对这条信息准确性的信心（0.5-1.0）
- 如果没有值得记住的信息，返回空列表"""


class AgentReflector:
    def __init__(
        self,
        config: ReflectorConfig | None = None,
        llm_helper=None,
    ):
        self._config = config or ReflectorConfig()
        self._llm = llm_helper

    def reflect(
        self,
        user_input: str,
        assistant_response: str,
        tool_calls: list[dict] | None = None,
    ) -> Reflection:
        """根据对话复杂度选择反思深度。"""
        if self._is_deep_worthy(user_input, assistant_response, tool_calls):
            return self._deep_reflect(user_input, assistant_response, tool_calls)
        return self._shallow_reflect(user_input, assistant_response, tool_calls)

    def _is_deep_worthy(
        self,
        user_input: str,
        assistant_response: str,
        tool_calls: list[dict] | None,
    ) -> bool:
        """判断是否需要深度反思。"""
        if not self._config.enabled:
            return False
        if self._llm is None:
            return False
        # 有工具调用 → 深度反思
        if tool_calls:
            return True
        # 回复超过阈值 → 深度反思
        if len(assistant_response) > self._config.deep_threshold:
            return True
        # 用户输入包含偏好/事实关键词
        preference_keywords = ("喜欢", "不喜欢", "偏好", "讨厌", "爱", "恨")
        fact_keywords = ("我是", "我在", "我住", "我叫", "我的工作", "我今年")
        if any(kw in user_input for kw in preference_keywords + fact_keywords):
            return True
        return False

    def _shallow_reflect(
        self,
        user_input: str,
        assistant_response: str,
        tool_calls: list[dict] | None,
    ) -> Reflection:
        """轻量反思：规则提取，不调用 LLM。"""
        key_points = self._extract_key_points(user_input, assistant_response)
        needs_continue = self._should_continue(assistant_response, tool_calls)
        summary = self._generate_summary(user_input, assistant_response)
        return Reflection(
            needs_continue=needs_continue,
            summary=summary,
            key_points=key_points,
        )

    def _deep_reflect(
        self,
        user_input: str,
        assistant_response: str,
        tool_calls: list[dict] | None,
    ) -> Reflection:
        """深度反思：调用 LLM 提取结构化记忆。"""
        user_prompt = f"用户: {user_input}\n助手: {assistant_response}"
        if tool_calls:
            tool_info = ", ".join(c.get("name", "") for c in tool_calls)
            user_prompt += f"\n使用工具: {tool_info}"

        result = self._llm.judge_json(
            _REFLECT_SYSTEM_PROMPT,
            user_prompt,
            max_tokens=self._config.reflect_max_tokens,
        )

        memories: list[MemoryEntry] = []
        if result and "memories" in result:
            for m in result["memories"]:
                mem_type = m.get("type", "topic")
                if mem_type in self._config.extract_types:
                    memories.append(MemoryEntry(
                        type=mem_type,
                        content=m.get("content", ""),
                        confidence=m.get("confidence", 0.8),
                    ))

        key_points = result.get("key_points", []) if result else []
        if not key_points:
            key_points = self._extract_key_points(user_input, assistant_response)

        needs_continue = self._should_continue(assistant_response, tool_calls)
        summary = self._generate_summary(user_input, assistant_response)

        return Reflection(
            needs_continue=needs_continue,
            summary=summary,
            key_points=key_points,
            memories_to_store=memories,
        )

    def _extract_key_points(
        self, user_input: str, assistant_response: str
    ) -> list[str]:
        points: list[str] = []
        if len(assistant_response) > 50:
            sentences = assistant_response.split("。")
            for sent in sentences[:3]:
                sent = sent.strip()
                if len(sent) > 10:
                    points.append(sent)
        return points[:3]

    def _should_continue(
        self, response: str, tool_calls: list[dict] | None
    ) -> bool:
        if tool_calls:
            return len(tool_calls) > 0
        continuation_keywords = ("还有", "另外", "此外", "不过", "但是", "如果")
        return any(kw in response for kw in continuation_keywords)

    def _generate_summary(self, user_input: str, assistant_response: str) -> str:
        user_preview = user_input[:50] + "..." if len(user_input) > 50 else user_input
        response_preview = (
            assistant_response[:100] + "..."
            if len(assistant_response) > 100
            else assistant_response
        )
        return f"Q: {user_preview}\nA: {response_preview}"
