from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import re


@dataclass(frozen=True)
class MemoryCandidate:
    candidate_id: str
    content: str
    memory_type: str
    source: str
    confidence: float
    session_id: str
    turn_id: int
    trace_id: str = ""
    request_id: str = ""
    metadata: dict = field(default_factory=dict)


@dataclass(frozen=True)
class MemoryLedgerDecision:
    candidate: MemoryCandidate
    action: str
    reason: str
    normalized_content: str
    conflict: bool = False
    timestamp: datetime = field(default_factory=datetime.now)

    def to_log_details(self) -> dict:
        return {
            "candidate_id": self.candidate.candidate_id,
            "source": self.candidate.source,
            "memory_type": self.candidate.memory_type,
            "confidence": self.candidate.confidence,
            "action": self.action,
            "reason": self.reason,
            "conflict": self.conflict,
            "turn_id": self.candidate.turn_id,
            "content_preview": self.candidate.content[:120],
            "normalized_preview": self.normalized_content[:120],
        }


class MemoryLedgerEvaluator:
    _SHORT_TERM_MARKERS = ("先不要", "只讨论", "这次", "临时", "暂时")
    _EXPLICIT_MARKERS = ("记住", "以后", "长期", "一直", "永远")

    def evaluate(self, candidates: list[MemoryCandidate]) -> list[MemoryLedgerDecision]:
        decisions: list[MemoryLedgerDecision] = []
        seen: set[tuple[str, str]] = set()
        promoted_by_type: dict[str, list[str]] = {}
        for candidate in candidates:
            normalized = normalize_memory_content(candidate.content)
            key = (candidate.memory_type, normalized)
            if key in seen:
                decision = MemoryLedgerDecision(
                    candidate=candidate,
                    action="skip",
                    reason="duplicate_candidate",
                    normalized_content=normalized,
                )
            elif self._is_short_term_constraint(candidate):
                decision = MemoryLedgerDecision(
                    candidate=candidate,
                    action="skip",
                    reason="short_term_constraint",
                    normalized_content=normalized,
                )
            elif candidate.confidence < 0.8:
                decision = MemoryLedgerDecision(
                    candidate=candidate,
                    action="skip",
                    reason="low_confidence",
                    normalized_content=normalized,
                )
            else:
                conflict = self._has_possible_conflict(
                    normalized,
                    promoted_by_type.get(candidate.memory_type, []),
                )
                decision = MemoryLedgerDecision(
                    candidate=candidate,
                    action="promote",
                    reason="possible_conflict" if conflict else self._promotion_reason(candidate),
                    normalized_content=normalized,
                    conflict=conflict,
                )
                seen.add(key)
                promoted_by_type.setdefault(candidate.memory_type, []).append(normalized)
            decisions.append(decision)
        return decisions

    def _is_short_term_constraint(self, candidate: MemoryCandidate) -> bool:
        text = candidate.content
        return candidate.memory_type == "constraint" and any(
            marker in text for marker in self._SHORT_TERM_MARKERS
        )

    def _promotion_reason(self, candidate: MemoryCandidate) -> str:
        if any(marker in candidate.content for marker in self._EXPLICIT_MARKERS):
            return "explicit_memory"
        return "stable_candidate"

    def _has_possible_conflict(self, normalized: str, previous_items: list[str]) -> bool:
        if "不喜欢" not in normalized:
            return False
        positive = normalized.replace("不喜欢", "喜欢")
        return positive in previous_items


def normalize_memory_content(content: str) -> str:
    text = re.sub(r"\s+", " ", str(content or "")).strip()
    return text.rstrip("。.!！?？；;，, ")
