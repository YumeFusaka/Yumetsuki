from llm.text_processor import ProcessedText

from config.schema import LLMConfig
from core.log_types import LogChannel
from agent.manager import AgentManager
from llm.adapter import LLMStreamChunk
from llm.manager import LLMManager
from session.context import SessionContext
from session.manager import SessionContextManager


class _RecordingLogService:
    def __init__(self):
        self.events = []

    def record(self, event):
        self.events.append(event)


class _StreamingAdapter:
    def stream_chat(self, _messages, tools=None):
        yield LLMStreamChunk(content="你好")
        yield LLMStreamChunk(content="，世界")


class _ManyChunkStreamingAdapter:
    def stream_chat(self, _messages, tools=None):
        for _ in range(20):
            yield LLMStreamChunk(content="啊")


class _FakeLLMManager:
    def __init__(self, *args, final_text="[emotion:开心]好的", **kwargs):
        self.final_text = final_text
        self.calls = []

    def chat_stream(self, user_input, session_context="", extra_context="", allow_tools=True):
        self.calls.append(
            {
                "user_input": user_input,
                "session_context": session_context,
                "extra_context": extra_context,
                "allow_tools": allow_tools,
            }
        )
        yield ProcessedText(clean_text=self.final_text.replace("[emotion:开心]", ""), emotion="开心")

    def set_character(self, *_args, **_kwargs):
        return None


class FakePlanner:
    def __init__(self, plan):
        self.plan_value = plan

    def plan(self, _user_input, _tools):
        return self.plan_value


class FakeExecutor:
    def __init__(self, result):
        self.result = result

    def execute(self, _plan, _tool_registry):
        return self.result


class FakePlan:
    def __init__(self, mode="chat", goal="reply"):
        self.mode = mode
        self.goal = goal
        self.tool_name = None
        self.arguments = None
        self.needs_multi_step = False
        self.steps = []


def test_agent_manager_records_conversation_log_for_user_and_reply(monkeypatch):
    llm = _FakeLLMManager("[emotion:开心]收到")
    manager = AgentManager(
        llm_manager=llm,
        planner=FakePlanner(FakePlan(mode="chat", goal="reply")),
        executor=FakeExecutor(""),
        memory_store=None,
        tool_registry=None,
        user_id="u1",
    )
    recorded = []
    monkeypatch.setattr(
        manager,
        "_record_log_event",
        lambda **kwargs: recorded.append(kwargs),
        raising=False,
    )

    list(manager.chat_stream("测试输入"))

    event_types = [
        item["event_type"]
        for item in recorded
        if item["channel"] == LogChannel.CONVERSATION
    ]
    assert "conversation.user_input" in event_types
    assert "conversation.assistant_reply" in event_types


def test_agent_manager_conversation_reply_log_contains_emotion_tool_and_memory_metadata(monkeypatch):
    llm = _FakeLLMManager("[emotion:开心]收到")
    plan = FakePlan(mode="tool", goal="reply")
    plan.tool_name = "notes__search"
    manager = AgentManager(
        llm_manager=llm,
        planner=FakePlanner(plan),
        executor=FakeExecutor("找到记录"),
        memory_store=type("M", (), {"search_relevant": lambda self, *_args, **_kwargs: ["记忆1"]})(),
        tool_registry=None,
        user_id="u1",
    )
    recorded = []
    monkeypatch.setattr(
        manager,
        "_record_log_event",
        lambda **kwargs: recorded.append(kwargs),
        raising=False,
    )

    list(manager.chat_stream("测试输入"))

    reply_event = next(item for item in recorded if item["event_type"] == "conversation.assistant_reply")
    assert reply_event["details"]["emotion"] == "开心"
    assert reply_event["details"]["tool_names"] == ["notes__search"]
    assert reply_event["details"]["memory_count"] == 1


def test_agent_manager_records_system_log_for_memory_retrieval_summary():
    log_service = _RecordingLogService()
    llm = _FakeLLMManager("[emotion:开心]收到")
    memory_store = type(
        "M",
        (),
        {
            "search_relevant": lambda self, *_args, **_kwargs: [
                "用户喜欢热茶",
                "用户最近在整理书房",
            ]
        },
    )()
    manager = AgentManager(
        llm_manager=llm,
        planner=FakePlanner(FakePlan(mode="chat", goal="reply")),
        executor=FakeExecutor(""),
        memory_store=memory_store,
        tool_registry=None,
        user_id="u1",
        session_id="s1",
        log_service=log_service,
    )

    list(manager.chat_stream("测试输入"))

    event = next(item for item in log_service.events if item.event_type == "memory.retrieved")
    assert event.channel == LogChannel.SYSTEM
    assert event.source == "agent.manager"
    assert event.session_id == "s1"
    assert event.details["count"] == 2
    assert "用户喜欢热茶" in event.details["preview"]


def test_session_context_manager_records_prompt_context_built_log():
    log_service = _RecordingLogService()
    manager = SessionContextManager(log_service=log_service)
    ctx = SessionContext.new(session_id="s1", user_id="u1")
    manager.record_user_input(ctx, "记住我喜欢红茶")

    prompt_context = manager.build_prompt_context(ctx)

    event = next(item for item in log_service.events if item.event_type == "session.prompt_context_built")
    assert event.channel == LogChannel.SYSTEM
    assert event.source == "session.manager"
    assert event.session_id == "s1"
    assert event.details["recent_turn_count"] == 1
    assert event.details["working_fact_count"] == 1
    assert prompt_context[:40] in event.details["preview"]


def test_llm_manager_records_stream_progress_during_content_accumulation(monkeypatch):
    log_service = _RecordingLogService()
    monkeypatch.setattr(LLMManager, "_create_adapter", lambda self, _config: _StreamingAdapter())
    manager = LLMManager(LLMConfig(), log_service=log_service, session_id="s1")

    list(manager.chat_stream("测试输入"))

    events = [item for item in log_service.events if item.event_type == "llm.stream_progress"]
    assert events
    assert events[-1].channel == LogChannel.SYSTEM
    assert events[-1].source == "llm.manager"
    assert events[-1].session_id == "s1"
    assert events[-1].details["response_length"] == len("你好，世界")
    assert events[-1].details["tail_preview"] == "你好，世界"


def test_llm_manager_throttles_stream_progress_logs(monkeypatch):
    log_service = _RecordingLogService()
    monkeypatch.setattr(LLMManager, "_create_adapter", lambda self, _config: _ManyChunkStreamingAdapter())
    manager = LLMManager(LLMConfig(), log_service=log_service, session_id="s1")

    list(manager.chat_stream("测试输入"))

    events = [item for item in log_service.events if item.event_type == "llm.stream_progress"]
    assert events
    assert len(events) < 20
