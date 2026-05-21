from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Reflection:
    needs_continue: bool
    summary: str
    key_points: list[str]


class AgentReflector:
    def reflect(
        self,
        user_input: str,
        assistant_response: str,
        tool_calls: list[dict] | None = None,
    ) -> Reflection:
        key_points = self._extract_key_points(user_input, assistant_response)
        needs_continue = self._should_continue(assistant_response, tool_calls)
        summary = self._generate_summary(user_input, assistant_response)
        return Reflection(
            needs_continue=needs_continue,
            summary=summary,
            key_points=key_points,
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
