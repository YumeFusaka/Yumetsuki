from unittest.mock import MagicMock, patch

from agent.manager import AgentManager, AgentEvents
from core.event_bus import EventBus
from llm.text_processor import ProcessedText


def test_new_event_constants_exist():
    assert hasattr(AgentEvents, "USER_INPUT")
    assert hasattr(AgentEvents, "ASSISTANT_REPLY")
    assert hasattr(AgentEvents, "THINKING")
    assert AgentEvents.USER_INPUT == "agent.user_input"
    assert AgentEvents.ASSISTANT_REPLY == "agent.assistant_reply"
    assert AgentEvents.THINKING == "agent.thinking"


def test_stream_chunk_has_thinking_field():
    from llm.adapter import LLMStreamChunk
    chunk = LLMStreamChunk(thinking="我在思考...")
    assert chunk.thinking == "我在思考..."


def test_processed_text_has_thinking_field():
    from llm.text_processor import ProcessedText
    pt = ProcessedText(clean_text="hello", emotion=None, thinking="思考中")
    assert pt.thinking == "思考中"


def test_chat_stream_publishes_user_input_and_reply():
    """chat_stream 应发布 USER_INPUT 和 ASSISTANT_REPLY 事件。"""
    bus = EventBus()
    received = []
    bus.subscribe(AgentEvents.USER_INPUT, lambda d: received.append(("user", d)))
    bus.subscribe(AgentEvents.ASSISTANT_REPLY, lambda d: received.append(("reply", d)))

    mock_llm = MagicMock()
    mock_llm.chat_stream.return_value = iter([ProcessedText(clean_text="你好", emotion=None)])
    mock_llm._config = MagicMock()

    with patch.object(AgentManager, "_build_llm_helper", return_value=None):
        mgr = AgentManager(
            llm_manager=mock_llm,
            event_bus_instance=bus,
        )
    list(mgr.chat_stream("测试输入"))

    user_events = [e for e in received if e[0] == "user"]
    reply_events = [e for e in received if e[0] == "reply"]
    assert len(user_events) == 1
    assert user_events[0][1]["text"] == "测试输入"
    assert len(reply_events) == 1
    assert reply_events[0][1]["text"] == "你好"
