from agent.planner import AgentPlanner
from core.tool_registry import ToolEntry


def _tool(
    name: str,
    description: str,
    properties: dict | None = None,
    required: list[str] | None = None,
) -> ToolEntry:
    properties = properties if properties is not None else {"query": {"type": "string"}}
    required = required if required is not None else ["query"]
    return ToolEntry(
        name=name.split("__", 1)[-1],
        source="plugin",
        qualified_name=name,
        schema={
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
            },
        },
    )


def test_planner_prefers_chat_when_no_tool_matches():
    planner = AgentPlanner()
    plan = planner.plan("今天天气真好", [_tool("notes__search", "Search notes")])

    assert plan.mode == "chat"
    assert plan.tool_name is None


def test_planner_selects_tool_when_input_mentions_tool_intent():
    planner = AgentPlanner()
    plan = planner.plan("帮我搜索一下便签里的待办", [_tool("notes__search", "搜索便签内容")])

    assert plan.mode == "tool"
    assert plan.tool_name == "notes__search"
    assert plan.arguments == {"query": "帮我搜索一下便签里的待办"}


def test_planner_prefers_default_browser_search_tool():
    planner = AgentPlanner()
    tools = [
        _tool("web_automation__web_search_visible", "打开可见浏览器窗口并执行自动化搜索"),
        _tool("system_control__search_in_browser", "使用系统默认浏览器直接搜索关键词，适用于用浏览器搜索"),
    ]

    plan = planner.plan("用浏览器搜索 Python 教程", tools)

    assert plan.mode == "tool"
    assert plan.tool_name == "system_control__search_in_browser"
    assert plan.arguments == {"query": "Python 教程"}


def test_planner_extracts_default_browser_search_query_from_natural_phrases():
    planner = AgentPlanner()
    tools = [
        _tool("system_control__search_in_browser", "使用系统默认浏览器直接搜索关键词，适用于用浏览器搜索"),
    ]

    cases = {
        "搜索天气预报": "天气预报",
        "帮我搜索天气预报": "天气预报",
        "帮我搜一下天气预报": "天气预报",
        "帮我在浏览器里搜 天气预报": "天气预报",
        "使用浏览器搜索天气预报": "天气预报",
        "打开浏览器搜索 Python 教程": "Python 教程",
        "在浏览器里搜 今天新闻": "今天新闻",
        "浏览器查一下 PySide6 文档": "PySide6 文档",
    }

    for text, expected_query in cases.items():
        plan = planner.plan(text, tools)
        assert plan.mode == "tool"
        assert plan.tool_name == "system_control__search_in_browser"
        assert plan.arguments == {"query": expected_query}


def test_planner_normalizes_browser_search_query_after_llm_judge():
    class FakeLLMHelper:
        def judge_json(self, *_args, **_kwargs):
            return {
                "mode": "tool",
                "goal": "搜索",
                "tool_name": "system_control__search_in_browser",
                "arguments": {"query": "搜索天气预报"},
                "needs_multi_step": False,
                "steps": [],
            }

    planner = AgentPlanner(llm_helper=FakeLLMHelper())
    tools = [
        _tool("system_control__search_in_browser", "使用系统默认浏览器直接搜索关键词，适用于用浏览器搜索"),
    ]

    plan = planner.plan("搜索天气预报", tools)

    assert plan.mode == "tool"
    assert plan.tool_name == "system_control__search_in_browser"
    assert plan.arguments == {"query": "天气预报"}


def test_planner_does_not_open_new_browser_for_existing_browser_click_request():
    planner = AgentPlanner()
    tools = [
        _tool("system_control__open_browser", "打开默认浏览器", properties={}, required=[]),
        _tool("web_automation__web_session_open", "打开一个由 Playwright 控制的持续浏览器会话", properties={}, required=[]),
    ]

    plan = planner.plan("点击浏览器里的第二个条目", tools)

    assert plan.mode == "chat"
    assert plan.tool_name is None


def test_planner_does_not_search_when_user_asks_to_read_current_search_page():
    planner = AgentPlanner()
    tools = [
        _tool("system_control__search_in_browser", "使用系统默认浏览器直接搜索关键词，适用于用浏览器搜索"),
    ]

    plan = planner.plan("看看你搜索的这个页面有什么内容", tools)

    assert plan.mode == "chat"
    assert plan.tool_name is None


def test_planner_current_page_read_request_is_hard_guard_before_llm_judge():
    class FakeLLMHelper:
        def __init__(self):
            self.calls = []

        def judge_json(self, *_args, **_kwargs):
            self.calls.append(_args)
            return {
                "mode": "tool",
                "goal": "错误搜索",
                "tool_name": "system_control__search_in_browser",
                "arguments": {"query": "看看你搜索的这个页面有什么内容，然后总结一下"},
            }

    helper = FakeLLMHelper()
    planner = AgentPlanner(llm_helper=helper)
    tools = [
        _tool("system_control__search_in_browser", "使用系统默认浏览器直接搜索关键词，适用于用浏览器搜索"),
    ]

    plan = planner.plan("看看你搜索的这个页面有什么内容，然后总结一下", tools)

    assert helper.calls == []
    assert plan.mode == "chat"
    assert plan.tool_name is None


def test_planner_still_searches_when_user_explicitly_requests_new_search():
    planner = AgentPlanner()
    tools = [
        _tool("system_control__search_in_browser", "使用系统默认浏览器直接搜索关键词，适用于用浏览器搜索"),
    ]

    plan = planner.plan("重新搜索 魔仓杏铃", tools)

    assert plan.mode == "tool"
    assert plan.tool_name == "system_control__search_in_browser"
    assert plan.arguments == {"query": "魔仓杏铃"}


def test_planner_still_opens_browser_for_explicit_open_request():
    planner = AgentPlanner()
    tools = [
        _tool("system_control__open_browser", "打开默认浏览器", properties={}, required=[]),
    ]

    plan = planner.plan("打开浏览器", tools)

    assert plan.mode == "tool"
    assert plan.tool_name == "system_control__open_browser"
