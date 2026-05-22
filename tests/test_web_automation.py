from config.schema import AgentConfig, WebAutomationConfig


def test_web_automation_config_defaults():
    config = WebAutomationConfig()
    assert config.permission_level == "medium"
    assert config.default_engine == "bing"
    assert config.screenshot_dir == "data/screenshots"


def test_web_automation_config_in_agent_config():
    agent = AgentConfig()
    assert agent.web_automation.permission_level == "medium"
    assert agent.web_automation.default_engine == "bing"
