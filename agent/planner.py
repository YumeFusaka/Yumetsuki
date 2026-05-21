from __future__ import annotations

from dataclasses import dataclass, field
import re

from core.tool_registry import ToolEntry


@dataclass(frozen=True)
class AgentPlan:
    mode: str
    goal: str
    tool_name: str | None = None
    arguments: dict[str, object] = field(default_factory=dict)


class AgentPlanner:
    _TOOL_INTENT_KEYWORDS = (
        "搜索",
        "查",
        "查找",
        "查一下",
        "看看",
        "检索",
        "find",
        "search",
        "lookup",
    )

    def plan(self, user_input: str, tools: list[ToolEntry]) -> AgentPlan:
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
        for part in re.findall(r"[\u4e00-\u9fff]{2,}|[a-zA-Z0-9]+", normalized):
            tokens.append(part)
            if re.fullmatch(r"[\u4e00-\u9fff]{2,}", part):
                tokens.extend(self._cn_ngrams(part))
        return list(dict.fromkeys(token for token in tokens if len(token) >= 2))

    def _cn_ngrams(self, text: str) -> list[str]:
        grams: list[str] = []
        for size in range(2, min(5, len(text) + 1)):
            for index in range(0, len(text) - size + 1):
                grams.append(text[index:index + size])
        return grams
