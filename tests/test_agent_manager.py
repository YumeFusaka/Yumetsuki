from dataclasses import dataclass
import threading
import time

from agent.manager import AgentManager
from llm.text_processor import ProcessedText


@dataclass
class FakePlan:
    mode: str
    goal: str
    tool_name: str | None = None
    arguments: dict | None = None
    needs_multi_step: bool = False
    steps: list = None


class FakePlanner:
    def __init__(self, plan: FakePlan):
        self.plan_value = plan
        self.calls = []

    def plan(self, user_input, tools):
        self.calls.append({"user_input": user_input, "tools": tools})
        return self.plan_value


class FakeExecutor:
    def __init__(self, result: str):
        self.result = result
        self.calls = []

    def execute(self, plan, tool_registry):
        self.calls.append({"plan": plan, "tool_registry": tool_registry})
        return self.result


class FakeMemoryStore:
    def __init__(self, memories=None):
        self.memories = memories or []
        self.search_calls = []
        self.add_calls = []

    def search_relevant(self, query, user_id):
        self.search_calls.append({"query": query, "user_id": user_id})
        return self.memories

    def add_conversation(self, user_text, assistant_text, user_id):
        self.add_calls.append({
            "user_text": user_text,
            "assistant_text": assistant_text,
            "user_id": user_id,
        })


class SlowMemoryStore(FakeMemoryStore):
    def __init__(self):
        super().__init__([])
        self.started = threading.Event()
        self.release = threading.Event()

    def add_conversation(self, user_text, assistant_text, user_id):
        self.started.set()
        self.release.wait(timeout=1.0)
        super().add_conversation(user_text, assistant_text, user_id)


class FakeToolRegistry:
    def tool_specs(self):
        return [{"function": {"name": "notes__search"}}]

    def entries(self):
        return []


class FakeLLMManager:
    def __init__(self, final_text="[emotion:开心]好的"):
        self.final_text = final_text
        self.calls = []

    def chat_stream(self, user_input, extra_context="", allow_tools=True):
        self.calls.append({
            "user_input": user_input,
            "extra_context": extra_context,
            "allow_tools": allow_tools,
        })
        yield ProcessedText(clean_text=self.final_text.replace("[emotion:开心]", ""), emotion="开心")


def test_agent_manager_injects_memories_into_chat():
    manager = AgentManager(
        llm_manager=FakeLLMManager("[emotion:开心]我记得你喜欢樱花"),
        planner=FakePlanner(FakePlan(mode="chat", goal="reply")),
        executor=FakeExecutor(""),
        memory_store=FakeMemoryStore(["用户喜欢樱花主题"]),
        tool_registry=FakeToolRegistry(),
        user_id="u1",
    )

    results = list(manager.chat_stream("我喜欢什么主题？"))

    assert results[-1].clean_text == "我记得你喜欢樱花"
    assert "用户喜欢樱花主题" in manager._llm_manager.calls[0]["extra_context"]
    assert manager._memory_store.add_calls[0]["assistant_text"] == "我记得你喜欢樱花"


def test_agent_manager_executes_tool_then_calls_llm():
    manager = AgentManager(
        llm_manager=FakeLLMManager("[emotion:开心]我帮你查到了"),
        planner=FakePlanner(FakePlan(
            mode="tool",
            goal="search notes",
            tool_name="notes__search",
            arguments={"query": "待办"},
        )),
        executor=FakeExecutor("找到 3 条待办"),
        memory_store=FakeMemoryStore(),
        tool_registry=FakeToolRegistry(),
        user_id="u1",
    )

    results = list(manager.chat_stream("帮我看看待办"))

    assert results[-1].clean_text == "我帮你查到了"
    assert "找到 3 条待办" in manager._llm_manager.calls[0]["extra_context"]


def test_agent_manager_tool_mode_disables_followup_llm_tools():
    llm = FakeLLMManager("[emotion:开心]已经打开了")
    manager = AgentManager(
        llm_manager=llm,
        planner=FakePlanner(FakePlan(
            mode="tool",
            goal="open browser",
            tool_name="system_control__open_browser",
            arguments={},
        )),
        executor=FakeExecutor("已打开浏览器"),
        memory_store=FakeMemoryStore(),
        tool_registry=FakeToolRegistry(),
        user_id="u1",
    )

    results = list(manager.chat_stream("打开浏览器"))

    assert results[-1].clean_text == "已经打开了"
    assert llm.calls[0]["allow_tools"] is False
    assert "已打开浏览器" in llm.calls[0]["extra_context"]


def test_agent_manager_does_not_block_on_add_conversation():
    memory_store = SlowMemoryStore()
    manager = AgentManager(
        llm_manager=FakeLLMManager("[emotion:开心]马上完成"),
        planner=FakePlanner(FakePlan(mode="chat", goal="reply")),
        executor=FakeExecutor(""),
        memory_store=memory_store,
        tool_registry=FakeToolRegistry(),
        user_id="u1",
    )

    start = time.perf_counter()
    results = list(manager.chat_stream("测试一下"))
    elapsed = time.perf_counter() - start

    assert results[-1].clean_text == "马上完成"
    assert memory_store.started.is_set()
    assert elapsed < 0.5
    memory_store.release.set()
