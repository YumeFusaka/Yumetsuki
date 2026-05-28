from config.schema import SessionContextConfig
from session.context import ActiveTask, SessionContext, SessionSummary, SessionTurn, WorkingFact
from session.policy import SessionPolicy
from vision.types import VisualObservation


def test_session_context_starts_empty():
    ctx = SessionContext.new(session_id="s1", user_id="u1")

    assert ctx.session_id == "s1"
    assert ctx.user_id == "u1"
    assert ctx.turn_counter == 0
    assert ctx.recent_turns == []
    assert ctx.working_facts == []
    assert ctx.active_tasks == []
    assert ctx.visual_observations == []
    assert ctx.summary.current_topic == ""


def test_session_context_append_turn_increments_counter():
    ctx = SessionContext.new(session_id="s1", user_id="u1")

    turn = SessionTurn.user(turn_id=1, text="先讨论方案")
    ctx.append_turn(turn)

    assert ctx.turn_counter == 1
    assert ctx.recent_turns[-1].text == "先讨论方案"
    assert ctx.recent_turns[-1].role == "user"


def test_policy_extracts_high_priority_user_constraint():
    ctx = SessionContext.new(session_id="s1", user_id="u1")
    policy = SessionPolicy()

    policy.record_user_input(ctx, "先不要改代码，只讨论方案。")

    assert any(f.category == "constraint" for f in ctx.working_facts)
    assert any("只讨论方案" in f.content for f in ctx.working_facts)


def test_policy_build_prompt_context_contains_recent_turns_and_summary():
    ctx = SessionContext.new(session_id="s1", user_id="u1")
    policy = SessionPolicy()
    policy.record_user_input(ctx, "先讨论性能问题")
    policy.record_assistant_reply(ctx, "好，我们先分析性能。")

    prompt_context = policy.build_prompt_context(ctx)

    assert "当前会话短期上下文" in prompt_context
    assert "先讨论性能问题" in prompt_context
    assert "好，我们先分析性能。" in prompt_context


def test_session_context_prompt_includes_recent_visual_observation():
    ctx = SessionContext.new(session_id="s1", user_id="u1")
    ctx.visual_observations.append(VisualObservation(
        text="屏幕上显示登录失败",
        source="screen_ocr",
        image_path="data/vision/a.png",
        timestamp=1.0,
    ))

    prompt = SessionPolicy().build_prompt_context(ctx)

    assert "最近视觉信息" in prompt
    assert "screen_ocr: 屏幕上显示登录失败" in prompt


def test_policy_collects_only_stable_mem0_candidates():
    ctx = SessionContext.new(session_id="s1", user_id="u1")
    policy = SessionPolicy()

    policy.record_user_input(ctx, "记住，我以后都不想看长篇回答。")
    candidates = policy.collect_mem0_candidates(ctx)

    assert len(candidates) == 1
    assert "不想看长篇回答" in candidates[0].content


def test_policy_does_not_collect_short_term_constraint_as_mem0_candidate():
    ctx = SessionContext.new(session_id="s1", user_id="u1")
    policy = SessionPolicy()

    policy.record_user_input(ctx, "先不要改代码，只讨论方案。")

    assert policy.collect_mem0_candidates(ctx) == []


def test_policy_trims_recent_turns_to_configured_limit():
    ctx = SessionContext.new(session_id="s1", user_id="u1")
    policy = SessionPolicy(
        SessionContextConfig(
            recent_turns_limit=2,
            working_facts_limit=12,
            prompt_facts_limit=3,
            prompt_turns_limit=2,
            constraint_ttl_turns=12,
            mem0_promotion_importance=0.9,
        )
    )

    policy.record_user_input(ctx, "第一句")
    policy.record_assistant_reply(ctx, "回复一")
    policy.record_user_input(ctx, "第二句")

    assert [turn.text for turn in ctx.recent_turns] == ["回复一", "第二句"]


def test_policy_trims_working_facts_to_configured_limit():
    ctx = SessionContext.new(session_id="s1", user_id="u1")
    policy = SessionPolicy(
        SessionContextConfig(
            recent_turns_limit=8,
            working_facts_limit=1,
            prompt_facts_limit=3,
            prompt_turns_limit=2,
            constraint_ttl_turns=12,
            mem0_promotion_importance=0.9,
        )
    )

    policy.record_user_input(ctx, "先不要改代码。")
    policy.record_user_input(ctx, "记住，我以后都不想看长篇回答。")

    assert len(ctx.working_facts) == 1
    assert ctx.working_facts[0].category == "preference"
