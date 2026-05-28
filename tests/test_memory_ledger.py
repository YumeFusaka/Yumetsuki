from memory.ledger import MemoryCandidate, MemoryLedgerEvaluator


def test_memory_ledger_promotes_explicit_preference():
    evaluator = MemoryLedgerEvaluator()
    candidate = MemoryCandidate(
        candidate_id="c1",
        content="记住，我以后都不想看长篇回答。",
        memory_type="preference",
        source="working_fact",
        confidence=0.95,
        session_id="s1",
        turn_id=1,
    )

    decisions = evaluator.evaluate([candidate])

    assert decisions[0].action == "promote"
    assert decisions[0].reason == "explicit_memory"
    assert decisions[0].normalized_content == "记住，我以后都不想看长篇回答"


def test_memory_ledger_skips_short_term_constraint():
    evaluator = MemoryLedgerEvaluator()
    candidate = MemoryCandidate(
        candidate_id="c1",
        content="先不要改代码，只讨论方案。",
        memory_type="constraint",
        source="working_fact",
        confidence=0.95,
        session_id="s1",
        turn_id=1,
    )

    decisions = evaluator.evaluate([candidate])

    assert decisions[0].action == "skip"
    assert decisions[0].reason == "short_term_constraint"


def test_memory_ledger_skips_duplicate_candidates():
    evaluator = MemoryLedgerEvaluator()
    candidates = [
        MemoryCandidate(
            candidate_id="c1",
            content="记住，我喜欢樱花主题。",
            memory_type="preference",
            source="working_fact",
            confidence=0.95,
            session_id="s1",
            turn_id=1,
        ),
        MemoryCandidate(
            candidate_id="c2",
            content="记住，我喜欢樱花主题",
            memory_type="preference",
            source="working_fact",
            confidence=0.95,
            session_id="s1",
            turn_id=2,
        ),
    ]

    decisions = evaluator.evaluate(candidates)

    assert [item.action for item in decisions] == ["promote", "skip"]
    assert decisions[1].reason == "duplicate_candidate"


def test_memory_ledger_marks_possible_conflict_without_deleting_old_memory():
    evaluator = MemoryLedgerEvaluator()
    candidates = [
        MemoryCandidate(
            candidate_id="c1",
            content="记住，我喜欢长篇解释。",
            memory_type="preference",
            source="working_fact",
            confidence=0.95,
            session_id="s1",
            turn_id=1,
        ),
        MemoryCandidate(
            candidate_id="c2",
            content="记住，我不喜欢长篇解释。",
            memory_type="preference",
            source="working_fact",
            confidence=0.95,
            session_id="s1",
            turn_id=2,
        ),
    ]

    decisions = evaluator.evaluate(candidates)

    assert decisions[1].action == "promote"
    assert decisions[1].conflict is True
    assert decisions[1].reason == "possible_conflict"
