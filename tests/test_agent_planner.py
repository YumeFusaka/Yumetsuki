from agent.planner import AgentPlanner
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
