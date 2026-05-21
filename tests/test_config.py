from pathlib import Path
from config.manager import ConfigManager
from config.schema import MCPServerConfig


def test_load_default_config(tmp_path):
    api_yaml = tmp_path / "api.yaml"
    api_yaml.write_text("""
llm:
  provider: openai_compat
  model: test-model
  api_key: sk-test
  base_url: http://localhost:8000/v1
  stream: true
  temperature: 0.7
  max_tokens: 2048
tts:
  engine: none
  api_url: http://127.0.0.1:9880
""")
    sys_yaml = tmp_path / "system_config.yaml"
    sys_yaml.write_text("""
language: zh-CN
theme: dark
font_family: Microsoft YaHei
font_size: 14
""")
    mgr = ConfigManager(config_dir=tmp_path)
    assert mgr.api.llm.model == "test-model"
    assert mgr.api.llm.api_key == "sk-test"
    assert mgr.system.theme == "dark"


def test_save_config(tmp_path):
    api_yaml = tmp_path / "api.yaml"
    api_yaml.write_text("""
llm:
  provider: openai_compat
  model: old
  api_key: ""
  base_url: http://localhost/v1
  stream: true
  temperature: 0.7
  max_tokens: 2048
tts:
  engine: none
  api_url: http://127.0.0.1:9880
""")
    sys_yaml = tmp_path / "system_config.yaml"
    sys_yaml.write_text("language: zh-CN\ntheme: dark\nfont_family: Microsoft YaHei\nfont_size: 14\n")

    mgr = ConfigManager(config_dir=tmp_path)
    mgr.api.llm.model = "new-model"
    mgr.save()

    mgr2 = ConfigManager(config_dir=tmp_path)
    assert mgr2.api.llm.model == "new-model"


def test_load_and_save_mcp_config(tmp_path):
    mcp_yaml = tmp_path / "mcp.yaml"
    mcp_yaml.write_text("""
servers:
  - name: local-tools
    transport: stdio
    command: python server.py
    url: ""
    enabled: true
""")

    mgr = ConfigManager(config_dir=tmp_path)
    assert len(mgr.mcp.servers) == 1
    assert mgr.mcp.servers[0].name == "local-tools"
    assert mgr.mcp.servers[0].transport == "stdio"

    mgr.mcp.servers.append(MCPServerConfig(
        name="remote-tools",
        transport="sse",
        url="http://127.0.0.1:8000/sse",
    ))
    mgr.save()

    mgr2 = ConfigManager(config_dir=tmp_path)
    assert [server.name for server in mgr2.mcp.servers] == ["local-tools", "remote-tools"]
    assert mgr2.mcp.servers[1].url == "http://127.0.0.1:8000/sse"


def test_save_mcp_does_not_create_api_config(tmp_path):
    mgr = ConfigManager(config_dir=tmp_path)
    mgr.mcp.servers.append(MCPServerConfig(name="tools", command="python server.py"))
    mgr.save_mcp()

    assert (tmp_path / "mcp.yaml").exists()
    assert not (tmp_path / "api.yaml").exists()


def test_save_api_does_not_create_system_config(tmp_path):
    mgr = ConfigManager(config_dir=tmp_path)
    mgr.api.llm.model = "api-only"
    mgr.save_api()

    assert (tmp_path / "api.yaml").exists()
    assert not (tmp_path / "system_config.yaml").exists()


def test_save_system_does_not_create_api_config(tmp_path):
    mgr = ConfigManager(config_dir=tmp_path)
    mgr.system.font_size = 18
    mgr.save_system()

    assert (tmp_path / "system_config.yaml").exists()
    assert not (tmp_path / "api.yaml").exists()
