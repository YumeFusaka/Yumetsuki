import pytest
from config.schema import AgentConfig, SystemControlConfig


def test_system_control_config_defaults():
    config = SystemControlConfig()
    assert config.permission_level == "low"


def test_system_control_config_in_agent_config():
    agent = AgentConfig()
    assert agent.system_control.permission_level == "low"


def test_system_control_config_accepts_valid_levels():
    for level in ("low", "medium", "high"):
        config = SystemControlConfig(permission_level=level)
        assert config.permission_level == level
