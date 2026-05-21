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
