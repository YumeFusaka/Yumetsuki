from pathlib import Path
from config.manager import ConfigManager
from config.schema import ASRConfig, MCPServerConfig, SystemConfig


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


def test_save_and_reload_extended_tts_config(tmp_path):
    mgr = ConfigManager(config_dir=tmp_path)
    mgr.api.tts.engine = "gptsovits"
    mgr.api.tts.api_url = "http://127.0.0.1:9880"
    mgr.api.tts.audio_mode = "pcm_stream"
    mgr.api.tts.ref_audio_path = "data/audio/ref.wav"
    mgr.api.tts.reference_mode = "session_preload"
    mgr.api.tts.prompt_lang = "zh"
    mgr.api.tts.output_lang = "en"
    mgr.api.tts.prompt_text = "你好，我是参考音频"
    mgr.save_api()

    mgr2 = ConfigManager(config_dir=tmp_path)
    assert mgr2.api.tts.engine == "gptsovits"
    assert mgr2.api.tts.api_url == "http://127.0.0.1:9880"
    assert mgr2.api.tts.audio_mode == "pcm_stream"
    assert mgr2.api.tts.ref_audio_path == "data/audio/ref.wav"
    assert mgr2.api.tts.reference_mode == "session_preload"
    assert mgr2.api.tts.prompt_lang == "zh"
    assert mgr2.api.tts.output_lang == "en"
    assert mgr2.api.tts.prompt_text == "你好，我是参考音频"


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


def test_load_default_memory_config(tmp_path):
    mgr = ConfigManager(config_dir=tmp_path)

    assert mgr.memory.enabled is False
    assert mgr.memory.storage_dir == "data/memory"
    assert mgr.memory.user_id == "default-user"
    assert mgr.memory.top_k == 5


def test_save_and_reload_memory_config(tmp_path):
    mgr = ConfigManager(config_dir=tmp_path)
    mgr.memory.enabled = True
    mgr.memory.storage_dir = "runtime/memory"
    mgr.memory.user_id = "alice"
    mgr.memory.top_k = 8
    mgr.save_memory()

    mgr2 = ConfigManager(config_dir=tmp_path)
    assert mgr2.memory.enabled is True
    assert mgr2.memory.storage_dir == "runtime/memory"
    assert mgr2.memory.user_id == "alice"
    assert mgr2.memory.top_k == 8


def test_system_config_exposes_logging_runtime():
    cfg = SystemConfig()

    assert hasattr(cfg, "logging")
    assert cfg.logging.enabled is True
    assert cfg.logging.log_root == "data/logs"
    assert cfg.logging.system_flush_interval_ms == 200


def test_system_config_exposes_phase5_display_and_passive_settings():
    cfg = SystemConfig()

    assert cfg.chat_display.font_scale == 1.0
    assert cfg.chat_display.bubble_scale == 1.0
    assert cfg.passive_interaction.idle_threshold_seconds == 300
    assert cfg.passive_interaction.bubble_max_width == 280
    assert cfg.passive_interaction.bubble_duration_seconds == 8
    assert not hasattr(cfg.passive_interaction, "enabled")


def test_save_and_reload_phase5_system_config(tmp_path):
    mgr = ConfigManager(config_dir=tmp_path)
    mgr.system.chat_display.font_scale = 1.25
    mgr.system.chat_display.bubble_scale = 1.1
    mgr.system.passive_interaction.idle_threshold_seconds = 180
    mgr.system.passive_interaction.bubble_max_width = 360
    mgr.system.passive_interaction.bubble_duration_seconds = 12
    mgr.save_system()

    mgr2 = ConfigManager(config_dir=tmp_path)

    assert mgr2.system.chat_display.font_scale == 1.25
    assert mgr2.system.chat_display.bubble_scale == 1.1
    assert mgr2.system.passive_interaction.idle_threshold_seconds == 180
    assert mgr2.system.passive_interaction.bubble_max_width == 360
    assert mgr2.system.passive_interaction.bubble_duration_seconds == 12


def test_asr_config_defaults_to_faster_whisper_local_service():
    cfg = ASRConfig()

    assert cfg.engine == "faster_whisper"
    assert cfg.api_url == "http://127.0.0.1:8000"
    assert cfg.model == "base"
    assert cfg.language == "zh"
    assert not hasattr(cfg, "base_url")
    assert not hasattr(cfg, "api_key")
    assert not hasattr(cfg, "model_path")
    assert cfg.record_timeout_seconds == 20
    assert cfg.silence_threshold == 0.02
    assert cfg.silence_duration_ms == 1200


def test_passive_interaction_config_uses_idle_threshold_not_enable_switch():
    cfg = SystemConfig()

    assert cfg.passive_interaction.idle_threshold_seconds == 300
    assert cfg.passive_interaction.bubble_max_width == 280
    assert cfg.passive_interaction.bubble_duration_seconds == 8
    assert not hasattr(cfg.passive_interaction, "enabled")
