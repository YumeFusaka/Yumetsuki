from pathlib import Path

from session.context import SessionContext
from session.policy import SessionPolicy
from session.store import SessionContextStore


def test_store_round_trips_context_to_sqlite(tmp_path: Path):
    store = SessionContextStore(tmp_path / "session.db")
    ctx = SessionContext.new(session_id="s1", user_id="u1")
    policy = SessionPolicy()
    policy.record_user_input(ctx, "今天先讨论记忆系统")

    store.save(ctx)
    loaded = store.load("u1", "s1")

    assert loaded is not None
    assert loaded.session_id == "s1"
    assert loaded.recent_turns[-1].text == "今天先讨论记忆系统"


def test_store_returns_none_for_unknown_session(tmp_path: Path):
    store = SessionContextStore(tmp_path / "session.db")
    assert store.load("u1", "missing") is None


def test_store_round_trips_working_facts(tmp_path: Path):
    store = SessionContextStore(tmp_path / "session.db")
    ctx = SessionContext.new(session_id="s1", user_id="u1")
    policy = SessionPolicy()
    policy.record_user_input(ctx, "先不要改代码，只讨论方案。")

    store.save(ctx)
    loaded = store.load("u1", "s1")

    assert loaded is not None
    assert len(loaded.working_facts) == 1
    assert loaded.working_facts[0].category == "constraint"
