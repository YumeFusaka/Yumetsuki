from agent.planner import AgentPlanner, AgentPlan
from config.schema import PlannerConfig
from core.tool_registry import ToolEntry


def _tool(name: str, description: str) -> ToolEntry:
    return ToolEntry(
        name=name.split("__", 1)[-1],
        source="plugin",
        qualified_name=name,
        schema={
            "description": description,
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
        },
    )


class FakeLLMHelper:
    """模拟 LLM helper，返回预设 JSON。"""
    def __init__(self, response: dict | None = None):
        self.response = response or {}
        self.calls = []

    def judge_json(self, system_prompt, user_prompt, max_tokens=200):
        self.calls.append({"system": system_prompt, "user": user_prompt})
        return self.response


# --- 快速路由测试 ---

def test_fast_route_simple_chat():
    """简单对话不触发 LLM 精判。"""
    helper = FakeLLMHelper()
    planner = AgentPlanner(
        config=PlannerConfig(llm_judge_enabled=True),
        llm_helper=helper,
    )
    plan = planner.plan("你好呀", [_tool("notes__search", "搜索便签")])

    assert plan.mode == "chat"
    assert len(helper.calls) == 0  # 未调用 LLM


def test_fast_route_no_llm_helper():
    """无 LLM helper 时只走快速路由。"""
    planner = AgentPlanner(config=PlannerConfig(llm_judge_enabled=True), llm_helper=None)
    plan = planner.plan("帮我搜索一下便签", [_tool("notes__search", "搜索便签")])

    assert plan.mode == "tool"
    assert plan.tool_name == "notes__search"


def test_fast_route_llm_judge_disabled():
    """LLM 精判关闭时只走快速路由。"""
    helper = FakeLLMHelper()
    planner = AgentPlanner(
        config=PlannerConfig(llm_judge_enabled=False),
        llm_helper=helper,
    )
    plan = planner.plan("帮我搜索一下便签", [_tool("notes__search", "搜索便签")])

    assert plan.mode == "tool"
    assert len(helper.calls) == 0


# --- LLM 精判触发测试 ---

def test_escalate_on_tool_match():
    """快速路由命中工具时触发 LLM 精判确认。"""
    helper = FakeLLMHelper(response={
        "mode": "tool",
        "goal": "搜索便签",
        "tool_name": "notes__search",
        "needs_multi_step": False,
        "steps": [],
    })
    planner = AgentPlanner(
        config=PlannerConfig(llm_judge_enabled=True),
        llm_helper=helper,
    )
    plan = planner.plan("帮我搜索一下便签里的待办", [_tool("notes__search", "搜索便签")])

    assert plan.mode == "tool"
    assert plan.tool_name == "notes__search"
    assert len(helper.calls) == 1  # 调用了 LLM


def test_escalate_on_complexity():
    """输入超过复杂度阈值时触发 LLM 精判。"""
    helper = FakeLLMHelper(response={
        "mode": "chat",
        "goal": "回复",
        "tool_name": None,
        "needs_multi_step": False,
        "steps": [],
    })
    planner = AgentPlanner(
        config=PlannerConfig(llm_judge_enabled=True, complexity_threshold=10),
        llm_helper=helper,
    )
    plan = planner.plan("今天天气真好，我想出去走走看看风景", [])

    assert plan.mode == "chat"
    assert len(helper.calls) == 1  # 超过阈值，触发了精判


def test_escalate_on_multi_action_pattern():
    """多动作模式触发 LLM 精判。"""
    helper = FakeLLMHelper(response={
        "mode": "multi_step",
        "goal": "查天气并提醒",
        "tool_name": None,
        "needs_multi_step": True,
        "steps": ["查询天气", "生成提醒"],
    })
    planner = AgentPlanner(
        config=PlannerConfig(llm_judge_enabled=True),
        llm_helper=helper,
    )
    plan = planner.plan("先帮我查一下天气，然后提醒我带伞", [_tool("weather__query", "查询天气")])

    assert plan.mode == "multi_step"
    assert plan.needs_multi_step is True
    assert len(plan.steps) == 2


def test_escalate_on_custom_keywords():
    """自定义触发关键词。"""
    helper = FakeLLMHelper(response={
        "mode": "chat",
        "goal": "分析",
        "tool_name": None,
        "needs_multi_step": False,
        "steps": [],
    })
    planner = AgentPlanner(
        config=PlannerConfig(llm_judge_enabled=True, extra_trigger_keywords=["分析", "总结"]),
        llm_helper=helper,
    )
    plan = planner.plan("帮我分析一下", [])

    assert len(helper.calls) == 1


# --- LLM 精判降级测试 ---

def test_llm_judge_failure_fallback():
    """LLM 精判返回空结果时降级为快速路由。"""
    helper = FakeLLMHelper(response={})  # 空结果
    planner = AgentPlanner(
        config=PlannerConfig(llm_judge_enabled=True),
        llm_helper=helper,
    )
    plan = planner.plan("帮我搜索便签", [_tool("notes__search", "搜索便签")])

    # 降级为快速路由结果
    assert plan.mode == "tool"
    assert plan.tool_name == "notes__search"


def test_llm_judge_invalid_tool_name_fallback():
    """LLM 返回不存在的工具名时降级为 chat。"""
    helper = FakeLLMHelper(response={
        "mode": "tool",
        "goal": "test",
        "tool_name": "nonexistent__tool",
        "needs_multi_step": False,
        "steps": [],
    })
    planner = AgentPlanner(
        config=PlannerConfig(llm_judge_enabled=True),
        llm_helper=helper,
    )
    plan = planner.plan("帮我搜索便签", [_tool("notes__search", "搜索便签")])

    # 工具名无效，降级为 chat
    assert plan.mode == "chat"
