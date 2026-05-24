from __future__ import annotations

from dataclasses import dataclass, field
from time import time


@dataclass
class SessionTurn:
    turn_id: int
    role: str
    text: str
    timestamp: float
    tokens_estimate: int = 0
    topic_tags: list[str] = field(default_factory=list)
    importance: float = 0.0

    @classmethod
    def user(cls, turn_id: int, text: str) -> "SessionTurn":
        return cls(turn_id=turn_id, role="user", text=text, timestamp=time())

    @classmethod
    def assistant(cls, turn_id: int, text: str) -> "SessionTurn":
        return cls(turn_id=turn_id, role="assistant", text=text, timestamp=time())


@dataclass
class WorkingFact:
    fact_id: str
    content: str
    category: str
    importance: float
    created_turn_id: int
    last_seen_turn_id: int
    ttl_turns: int
    source: str
    sticky: bool = False
    promoted_to_mem0: bool = False


@dataclass
class ActiveTask:
    task_id: str
    goal: str
    status: str
    current_step: str
    tool_name: str | None
    last_result: str
    created_turn_id: int
    updated_turn_id: int
    importance: float


@dataclass
class SessionSummary:
    current_topic: str = ""
    summary_text: str = ""
    mood_state: str = ""
    relationship_state: str = ""
    updated_turn_id: int = 0


@dataclass
class SessionContext:
    session_id: str
    user_id: str
    turn_counter: int = 0
    recent_turns: list[SessionTurn] = field(default_factory=list)
    working_facts: list[WorkingFact] = field(default_factory=list)
    active_tasks: list[ActiveTask] = field(default_factory=list)
    summary: SessionSummary = field(default_factory=SessionSummary)

    @classmethod
    def new(cls, session_id: str, user_id: str) -> "SessionContext":
        return cls(session_id=session_id, user_id=user_id)

    def append_turn(self, turn: SessionTurn) -> None:
        self.recent_turns.append(turn)
        self.turn_counter = max(self.turn_counter, turn.turn_id)
