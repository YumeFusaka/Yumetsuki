import tempfile
from pathlib import Path

import yaml

from config.manager import ConfigManager
from config.schema import AgentConfig, PlannerConfig, ProactiveConfig, ProactiveEventConfig


def test_agent_config_defaults():
    cfg = AgentConfig()
    assert cfg.planner.llm_judge_enabled is True
    assert cfg.planner.complexity_threshold == 80
    assert cfg.reflector.enabled is True
    assert cfg.reflector.deep_threshold == 30
    assert cfg.multi_step.max_steps == 3
    assert cfg.proactive.enabled is False
    assert cfg.proactive.idle_interval_minutes == 30


def test_agent_config_custom_values():
    cfg = AgentConfig(
        planner=PlannerConfig(complexity_threshold=120, extra_trigger_keywords=["分析", "总结"]),
        proactive=ProactiveConfig(
            enabled=True,
            idle_interval_minutes=15,
            events=[
                ProactiveEventConfig(name="morning", type="timer", prompt_template="早安"),
            ],
        ),
    )
    assert cfg.planner.complexity_threshold == 120
    assert cfg.planner.extra_trigger_keywords == ["分析", "总结"]
    assert cfg.proactive.enabled is True
    assert len(cfg.proactive.events) == 1
    assert cfg.proactive.events[0].name == "morning"


def test_config_manager_loads_agent_defaults(tmp_path):
    mgr = ConfigManager(config_dir=tmp_path)
    assert mgr.agent.planner.llm_judge_enabled is True
    assert mgr.agent.multi_step.enabled is True


def test_config_manager_loads_agent_from_yaml(tmp_path):
    agent_data = {
        "planner": {"llm_judge_enabled": False, "complexity_threshold": 50},
        "reflector": {"deep_threshold": 60},
        "multi_step": {"max_steps": 5, "total_timeout": 120},
        "proactive": {
            "enabled": True,
            "idle_interval_minutes": 20,
            "events": [
                {"name": "rest", "type": "timer", "condition": "60min", "prompt_template": "休息", "cooldown_minutes": 30},
            ],
        },
    }
    (tmp_path / "agent.yaml").write_text(yaml.dump(agent_data, allow_unicode=True), encoding="utf-8")

    mgr = ConfigManager(config_dir=tmp_path)
    assert mgr.agent.planner.llm_judge_enabled is False
    assert mgr.agent.planner.complexity_threshold == 50
    assert mgr.agent.reflector.deep_threshold == 60
    assert mgr.agent.multi_step.max_steps == 5
    assert mgr.agent.proactive.enabled is True
    assert mgr.agent.proactive.events[0].name == "rest"


def test_config_manager_saves_agent(tmp_path):
    mgr = ConfigManager(config_dir=tmp_path)
    mgr.agent.planner.complexity_threshold = 200
    mgr.agent.proactive.enabled = True
    mgr.save_agent()

    agent_path = tmp_path / "agent.yaml"
    assert agent_path.exists()

    loaded = yaml.safe_load(agent_path.read_text(encoding="utf-8"))
    assert loaded["planner"]["complexity_threshold"] == 200
    assert loaded["proactive"]["enabled"] is True
