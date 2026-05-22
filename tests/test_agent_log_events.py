from agent.manager import AgentEvents


def test_new_event_constants_exist():
    assert hasattr(AgentEvents, "USER_INPUT")
    assert hasattr(AgentEvents, "ASSISTANT_REPLY")
    assert hasattr(AgentEvents, "THINKING")
    assert AgentEvents.USER_INPUT == "agent.user_input"
    assert AgentEvents.ASSISTANT_REPLY == "agent.assistant_reply"
    assert AgentEvents.THINKING == "agent.thinking"
