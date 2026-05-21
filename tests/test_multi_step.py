import time

from agent.multi_step import MultiStepRunner, MultiStepResult, StepResult
from config.schema import MultiStepConfig


class FakeLLMHelper:
    def __init__(self, responses: list[dict] | None = None):
        self._responses = responses or []
        self._call_idx = 0
        self.calls = []

    def judge_json(self, system_prompt, user_prompt, max_tokens=200):
        self.calls.append({"system": system_prompt, "user": user_prompt})
        if self._call_idx < len(self._responses):
            resp = self._responses[self._call_idx]
            self._call_idx += 1
            return resp
        return {"action": "done"}


class FakeToolRegistry:
    def __init__(self, results: dict | None = None):
        self._results = results or {}
        self.calls = []

    def call_tool(self, name, arguments):
        self.calls.append({"name": name, "arguments": arguments})
        if name in self._results:
            return self._results[name]
        return f"result of {name}"


class FakeEventBus:
    def __init__(self):
        self.events = []

    def publish(self, event_name, data):
        self.events.append((event_name, data))


def test_multi_step_basic_flow():
    """基本多步推理：两步工具调用后完成。"""
    helper = FakeLLMHelper(responses=[
        {"action": "tool", "tool_name": "weather__query", "arguments": {"city": "北京"}, "description": "查询天气"},
        {"action": "tool", "tool_name": "notes__add", "arguments": {"text": "带伞"}, "description": "添加提醒"},
        {"action": "done"},
    ])
    registry = FakeToolRegistry(results={
        "weather__query": "北京今天有雨",
        "notes__add": "已添加",
    })
    bus = FakeEventBus()

    runner = MultiStepRunner(
        config=MultiStepConfig(max_steps=5, step_timeout=30, total_timeout=60),
        llm_helper=helper,
        tool_registry=registry,
        event_bus_instance=bus,
    )

    result = runner.run("查天气并提醒带伞", ["查询天气", "添加提醒"], [])

    assert len(result.steps_completed) == 2
    assert result.steps_completed[0].tool_name == "weather__query"
    assert result.steps_completed[0].tool_result == "北京今天有雨"
    assert result.steps_completed[1].tool_name == "notes__add"
    assert not result.timed_out
    assert not result.max_steps_reached
    assert "查询天气" in result.final_context


def test_multi_step_max_steps_reached():
    """达到最大步数时停止。"""
    helper = FakeLLMHelper(responses=[
        {"action": "tool", "tool_name": "t1", "arguments": {}, "description": "步骤1"},
        {"action": "tool", "tool_name": "t2", "arguments": {}, "description": "步骤2"},
        {"action": "tool", "tool_name": "t3", "arguments": {}, "description": "步骤3"},
    ])
    registry = FakeToolRegistry()

    runner = MultiStepRunner(
        config=MultiStepConfig(max_steps=2, step_timeout=30, total_timeout=60),
        llm_helper=helper,
        tool_registry=registry,
    )

    result = runner.run("测试", ["1", "2", "3"], [])

    assert len(result.steps_completed) == 2
    assert result.max_steps_reached is True


def test_multi_step_timeout():
    """总超时时停止，不执行后续步骤。"""
    helper = FakeLLMHelper(responses=[
        {"action": "tool", "tool_name": "t1", "arguments": {}, "description": "步骤1"},
        {"action": "tool", "tool_name": "t2", "arguments": {}, "description": "步骤2"},
        {"action": "tool", "tool_name": "t3", "arguments": {}, "description": "步骤3"},
    ])

    class SlowRegistry:
        def call_tool(self, name, arguments):
            time.sleep(0.05)  # 每步 50ms
            return "done"

    runner = MultiStepRunner(
        config=MultiStepConfig(max_steps=10, step_timeout=30, total_timeout=0.04),  # 40ms 超时
        llm_helper=helper,
        tool_registry=SlowRegistry(),
    )

    result = runner.run("测试超时", ["步骤1", "步骤2", "步骤3"], [])
    # 第一步执行后超时，不应执行全部 3 步
    assert result.timed_out is True
    assert len(result.steps_completed) < 3


def test_multi_step_tool_failure():
    """工具执行失败时继续下一步。"""
    helper = FakeLLMHelper(responses=[
        {"action": "tool", "tool_name": "broken", "arguments": {}, "description": "会失败"},
        {"action": "tool", "tool_name": "ok", "arguments": {}, "description": "正常"},
        {"action": "done"},
    ])

    class PartialRegistry:
        def call_tool(self, name, arguments):
            if name == "broken":
                raise RuntimeError("工具异常")
            return "成功"

    runner = MultiStepRunner(
        config=MultiStepConfig(max_steps=5, step_timeout=30, total_timeout=60),
        llm_helper=helper,
        tool_registry=PartialRegistry(),
    )

    result = runner.run("测试失败恢复", ["会失败", "正常"], [])

    assert len(result.steps_completed) == 2
    assert result.steps_completed[0].success is False
    assert result.steps_completed[1].success is True


def test_multi_step_no_llm_uses_initial_steps():
    """无 LLM helper 时按 initial_steps 顺序执行。"""
    registry = FakeToolRegistry()

    runner = MultiStepRunner(
        config=MultiStepConfig(max_steps=5),
        llm_helper=None,
        tool_registry=registry,
    )

    result = runner.run("测试", ["步骤A", "步骤B"], [])

    assert len(result.steps_completed) == 2
    assert result.steps_completed[0].description == "步骤A"
    assert result.steps_completed[1].description == "步骤B"


def test_multi_step_progress_events():
    """每步完成后发布进度事件。"""
    helper = FakeLLMHelper(responses=[
        {"action": "tool", "tool_name": "t1", "arguments": {}, "description": "第一步"},
        {"action": "done"},
    ])
    registry = FakeToolRegistry()
    bus = FakeEventBus()

    runner = MultiStepRunner(
        config=MultiStepConfig(max_steps=5),
        llm_helper=helper,
        tool_registry=registry,
        event_bus_instance=bus,
    )

    runner.run("测试事件", ["第一步"], [])

    progress_events = [e for e in bus.events if e[0] == "agent.multi_step_progress"]
    assert len(progress_events) == 1
    assert progress_events[0][1]["description"] == "第一步"
