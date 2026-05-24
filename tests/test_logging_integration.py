from PySide6.QtWidgets import QApplication

from llm.text_processor import ProcessedText

from config.schema import LLMConfig, TTSConfig
from core.log_types import LogChannel
from ui.chat.window import ChatWindow
from agent.manager import AgentManager


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


class _FakeAgentManager:
    def __init__(self, *args, **kwargs):
        pass

    def set_memory_store(self, *_args, **_kwargs):
        return None


class _FakeSpriteManager:
    def __init__(self, *args, **kwargs):
        pass

    def reload(self, *_args, **_kwargs):
        return None

    def load_character(self, *_args, **_kwargs):
        return None

    def set_emotion(self, *_args, **_kwargs):
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


def _app() -> QApplication:
    app = QApplication.instance()
    return app or QApplication([])


def test_enqueue_tts_segment_records_system_log(monkeypatch):
    _app()
    monkeypatch.setattr("ui.chat.window.LLMManager", _FakeLLMManager)
    monkeypatch.setattr("ui.chat.window.AgentManager", _FakeAgentManager)
    monkeypatch.setattr("ui.chat.window.SpriteManager", _FakeSpriteManager)

    chat_window = ChatWindow(
        LLMConfig(),
        tts_config=TTSConfig(engine="gptsovits", api_url="http://fake:9880"),
    )
    recorded = []
    monkeypatch.setattr(
        chat_window,
        "_record_log_event",
        lambda **kwargs: recorded.append(kwargs),
        raising=False,
    )
    monkeypatch.setattr(
        chat_window,
        "_start_tts_worker",
        lambda *_args, **_kwargs: None,
        raising=False,
    )

    chat_window._enqueue_tts_segment("你好。")

    assert recorded[0]["channel"] == LogChannel.SYSTEM
    assert recorded[0]["event_type"] == "tts.segment_enqueued"
    chat_window.close()


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
