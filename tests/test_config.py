from pathlib import Path
import yaml

from config.manager import ConfigManager
from config.schema import ASRConfig, MCPServerConfig, SystemConfig, VisionConfig


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


def test_mcp_server_config_has_runtime_diagnostics_defaults():
    cfg = MCPServerConfig(name="tools")

    assert cfg.connect_timeout_seconds == 10
    assert cfg.request_timeout_seconds == 10
    assert cfg.retry_attempts == 0


def test_load_mcp_runtime_options_from_yaml(tmp_path):
    mcp_yaml = tmp_path / "mcp.yaml"
    mcp_yaml.write_text(
        """
servers:
  - name: remote-tools
    transport: sse
    url: http://127.0.0.1:8000/mcp
    enabled: true
    connect_timeout_seconds: 3
    request_timeout_seconds: 5
    retry_attempts: 2
""",
        encoding="utf-8",
    )

    mgr = ConfigManager(tmp_path)

    server = mgr.mcp.servers[0]
    assert server.connect_timeout_seconds == 3
    assert server.request_timeout_seconds == 5
    assert server.retry_attempts == 2


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


def test_save_system_uses_atomic_replace(tmp_path, monkeypatch):
    mgr = ConfigManager(config_dir=tmp_path)
    calls = []

    def fake_replace(src, dst):
        calls.append((Path(src).name, Path(dst).name))

    monkeypatch.setattr("config.manager.os.replace", fake_replace)

    mgr.save_system()

    assert calls == [(".system_config.yaml.tmp", "system_config.yaml")]
    assert (tmp_path / ".system_config.yaml.tmp").exists()


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


def test_system_config_default_theme_is_sakura():
    cfg = SystemConfig()

    assert cfg.theme == "sakura"


def test_system_config_exposes_phase5_display_and_passive_settings():
    cfg = SystemConfig()

    assert cfg.chat_display.font_scale == 1.3
    assert cfg.chat_display.bubble_scale == 1.0
    assert cfg.passive_interaction.idle_threshold_seconds == 300
    assert cfg.passive_interaction.bubble_max_width == 600
    assert cfg.passive_interaction.bubble_duration_seconds == 8
    assert not hasattr(cfg.passive_interaction, "enabled")


def test_vision_config_defaults():
    cfg = SystemConfig()

    assert cfg.vision.enabled is False
    assert cfg.vision.ocr_engine == "rapidocr"
    assert cfg.vision.language == "ch"
    assert cfg.vision.screenshot_dir == "data/vision"
    assert cfg.vision.max_text_chars == 2000
    assert cfg.vision.explicit_trigger_only is True


def test_vision_config_maps_legacy_tesseract_engine_to_rapidocr():
    cfg = VisionConfig(ocr_engine="tesseract", language="chi_sim+eng")

    assert cfg.ocr_engine == "rapidocr"
    assert cfg.language == "ch"


def test_load_system_config_maps_legacy_tesseract_engine_to_rapidocr(tmp_path):
    sys_yaml = tmp_path / "system_config.yaml"
    sys_yaml.write_text(
        """
vision:
  enabled: true
  ocr_engine: tesseract
  tesseract_cmd: tesseract
  language: chi_sim+eng
  psm: 6
""",
        encoding="utf-8",
    )

    mgr = ConfigManager(config_dir=tmp_path)

    assert mgr.system.vision.enabled is True
    assert mgr.system.vision.ocr_engine == "rapidocr"
    assert mgr.system.vision.language == "ch"
    assert not hasattr(mgr.system.vision, "tesseract_cmd")
    assert not hasattr(mgr.system.vision, "psm")


def test_vision_config_unknown_ocr_engine_falls_back_to_rapidocr():
    cfg = VisionConfig(ocr_engine="unknown")

    assert cfg.ocr_engine == "rapidocr"


def test_save_and_reload_vision_system_config(tmp_path):
    mgr = ConfigManager(config_dir=tmp_path)
    mgr.system.vision.enabled = True
    mgr.system.vision.ocr_engine = "paddleocr"
    mgr.system.vision.language = "en"
    mgr.system.vision.screenshot_dir = "runtime/vision"
    mgr.system.vision.max_text_chars = 4200
    mgr.system.vision.explicit_trigger_only = False
    mgr.save_system()
    saved = yaml.safe_load((tmp_path / "system_config.yaml").read_text(encoding="utf-8"))

    mgr2 = ConfigManager(config_dir=tmp_path)

    assert saved["vision"]["enabled"] is True
    assert saved["vision"]["ocr_engine"] == "paddleocr"
    assert saved["vision"]["language"] == "en"
    assert saved["vision"]["explicit_trigger_only"] is True
    assert mgr2.system.vision.enabled is True
    assert mgr2.system.vision.ocr_engine == "paddleocr"
    assert mgr2.system.vision.language == "en"
    assert mgr2.system.vision.screenshot_dir == "runtime/vision"
    assert mgr2.system.vision.max_text_chars == 4200
    assert mgr2.system.vision.explicit_trigger_only is True


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


def test_asr_config_defaults_to_faster_whisper_local_model():
    cfg = ASRConfig()

    assert cfg.engine == "faster_whisper"
    assert cfg.model_path == "data/models/stt/faster-whisper-large-v3-turbo"
    assert cfg.device == "cpu"
    assert cfg.compute_type == "int8"
    assert cfg.transcribe_timeout_seconds == 120
    assert cfg.language == "zh"
    assert not hasattr(cfg, "base_url")
    assert not hasattr(cfg, "api_key")
    assert not hasattr(cfg, "api_url")
    assert not hasattr(cfg, "model")
    assert cfg.record_timeout_seconds == 20
    assert cfg.silence_threshold == 0.02
    assert cfg.silence_duration_ms == 1200


def test_passive_interaction_config_uses_idle_threshold_not_enable_switch():
    cfg = SystemConfig()

    assert cfg.passive_interaction.idle_threshold_seconds == 300
    assert cfg.passive_interaction.bubble_max_width == 600
    assert cfg.passive_interaction.bubble_duration_seconds == 8
    assert not hasattr(cfg.passive_interaction, "enabled")
