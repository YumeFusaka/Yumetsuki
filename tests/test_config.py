from pathlib import Path
from config.manager import ConfigManager


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
