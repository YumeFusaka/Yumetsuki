from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict
from pathlib import Path

from session.context import ActiveTask, SessionContext, SessionSummary, SessionTurn, WorkingFact
from vision.types import VisualObservation


class SessionContextStore:
    def __init__(self, db_path: Path):
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._db_path)

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS session_contexts ("
                "user_id TEXT, session_id TEXT, turn_counter INTEGER, summary_json TEXT, "
                "working_facts_json TEXT, active_tasks_json TEXT, "
                "PRIMARY KEY(user_id, session_id))"
            )
            conn.execute(
                "CREATE TABLE IF NOT EXISTS session_turns ("
                "user_id TEXT, session_id TEXT, turn_id INTEGER, role TEXT, text TEXT, "
                "PRIMARY KEY(user_id, session_id, turn_id, role))"
            )
            columns = [row[1] for row in conn.execute("PRAGMA table_info(session_contexts)").fetchall()]
            if "visual_observations_json" not in columns:
                conn.execute("ALTER TABLE session_contexts ADD COLUMN visual_observations_json TEXT DEFAULT '[]'")

    def save(self, ctx: SessionContext) -> None:
        with self._connect() as conn:
            conn.execute(
                "REPLACE INTO session_contexts("
                "user_id, session_id, turn_counter, summary_json, working_facts_json, "
                "active_tasks_json, visual_observations_json"
                ") "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    ctx.user_id,
                    ctx.session_id,
                    ctx.turn_counter,
                    json.dumps(asdict(ctx.summary), ensure_ascii=False),
                    json.dumps([asdict(fact) for fact in ctx.working_facts], ensure_ascii=False),
                    json.dumps([asdict(task) for task in ctx.active_tasks], ensure_ascii=False),
                    json.dumps([asdict(obs) for obs in ctx.visual_observations], ensure_ascii=False),
                ),
            )
            conn.execute(
                "DELETE FROM session_turns WHERE user_id=? AND session_id=?",
                (ctx.user_id, ctx.session_id),
            )
            conn.executemany(
                "INSERT INTO session_turns(user_id, session_id, turn_id, role, text) "
                "VALUES (?, ?, ?, ?, ?)",
                [
                    (ctx.user_id, ctx.session_id, turn.turn_id, turn.role, turn.text)
                    for turn in ctx.recent_turns
                ],
            )

    def load(self, user_id: str, session_id: str) -> SessionContext | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT turn_counter, summary_json, working_facts_json, active_tasks_json, "
                "visual_observations_json FROM session_contexts "
                "WHERE user_id=? AND session_id=?",
                (user_id, session_id),
            ).fetchone()
            if row is None:
                return None
            ctx = SessionContext.new(session_id=session_id, user_id=user_id)
            ctx.turn_counter = row[0]
            ctx.summary = SessionSummary(**json.loads(row[1]))
            ctx.working_facts = [WorkingFact(**item) for item in json.loads(row[2] or "[]")]
            ctx.active_tasks = [ActiveTask(**item) for item in json.loads(row[3] or "[]")]
            ctx.visual_observations = [VisualObservation(**item) for item in json.loads(row[4] or "[]")]
            turns = conn.execute(
                "SELECT turn_id, role, text FROM session_turns "
                "WHERE user_id=? AND session_id=? ORDER BY turn_id ASC",
                (user_id, session_id),
            ).fetchall()
            for turn_id, role, text in turns:
                ctx.recent_turns.append(
                    SessionTurn(turn_id=turn_id, role=role, text=text, timestamp=0.0)
                )
            return ctx
