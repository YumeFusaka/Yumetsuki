from config.schema import (
    AgentConfig,
    APIConfig,
    MCPConfig,
    MCPServerConfig,
    MemoryConfig,
    SystemConfig,
    VisionConfig,
)
from core.config_health import ConfigHealthChecker, HealthLevel


def _checker(project_root):
    return ConfigHealthChecker(project_root=project_root)


def _issue_text(issues):
    return "\n".join(f"{issue.message} {issue.details}" for issue in issues)


def test_config_health_flags_missing_stt_model_path(tmp_path):
    api = APIConfig()
    api.asr.engine = "faster_whisper"
    api.asr.model_path = "missing/stt-model"

    issues = _checker(tmp_path).check_all(api, SystemConfig(), MCPConfig(), MemoryConfig(), AgentConfig())

    assert any(issue.level == HealthLevel.ERROR and issue.code == "asr_model_missing" for issue in issues)


def test_config_health_accepts_existing_absolute_and_relative_stt_model_paths(tmp_path):
    model_dir = tmp_path / "models" / "stt"
    model_dir.mkdir(parents=True)

    relative_api = APIConfig()
    relative_api.asr.engine = "faster_whisper"
    relative_api.asr.model_path = "models/stt"
    absolute_api = APIConfig()
    absolute_api.asr.engine = "faster_whisper"
    absolute_api.asr.model_path = str(model_dir)

    relative_issues = _checker(tmp_path).check_all(
        relative_api,
        SystemConfig(),
        MCPConfig(),
        MemoryConfig(),
        AgentConfig(),
    )
    absolute_issues = _checker(tmp_path).check_all(
        absolute_api,
        SystemConfig(),
        MCPConfig(),
        MemoryConfig(),
        AgentConfig(),
    )

    assert not any(issue.code == "asr_model_missing" for issue in relative_issues)
    assert not any(issue.code == "asr_model_missing" for issue in absolute_issues)


def test_config_health_warns_about_non_baseline_tts_mode(tmp_path):
    api = APIConfig()
    api.asr.engine = "none"
    api.tts.engine = "gptsovits"
    api.tts.audio_mode = "pcm_stream"
    api.tts.reference_mode = "auto"

    issues = _checker(tmp_path).check_all(api, SystemConfig(), MCPConfig(), MemoryConfig(), AgentConfig())

    assert any(issue.level == HealthLevel.WARN and issue.code == "tts_experimental_mode" for issue in issues)
    assert not any(issue.level == HealthLevel.ERROR and issue.area == "api.tts" for issue in issues)


def test_config_health_does_not_warn_about_baseline_tts_mode(tmp_path):
    api = APIConfig()
    api.asr.engine = "none"
    api.tts.engine = "gptsovits"
    api.tts.audio_mode = "wav"
    api.tts.reference_mode = "inline"

    issues = _checker(tmp_path).check_all(api, SystemConfig(), MCPConfig(), MemoryConfig(), AgentConfig())

    assert not any(issue.code == "tts_experimental_mode" for issue in issues)


def test_config_health_flags_enabled_mcp_without_command_or_url(tmp_path):
    mcp = MCPConfig(
        servers=[
            MCPServerConfig(name="broken-stdio", transport="stdio", command="", enabled=True),
            MCPServerConfig(name="broken-sse", transport="sse", url="", enabled=True),
            MCPServerConfig(name="broken-http", transport="http", url="", enabled=True),
        ]
    )

    issues = _checker(tmp_path).check_all(APIConfig(), SystemConfig(), mcp, MemoryConfig(), AgentConfig())

    assert any(issue.level == HealthLevel.ERROR and issue.code == "mcp_stdio_command_missing" for issue in issues)
    assert sum(issue.code == "mcp_url_missing" for issue in issues) == 2


def test_config_health_ignores_disabled_mcp_server(tmp_path):
    mcp = MCPConfig(
        servers=[
            MCPServerConfig(name="disabled", transport="stdio", command="", enabled=False),
        ]
    )

    issues = _checker(tmp_path).check_all(APIConfig(), SystemConfig(), mcp, MemoryConfig(), AgentConfig())

    assert not any(issue.area == "mcp" for issue in issues)


def test_config_health_flags_invalid_mcp_request_timeout(tmp_path):
    mcp = MCPConfig(
        servers=[
            MCPServerConfig(
                name="timeout",
                transport="stdio",
                command="python server.py",
                request_timeout_seconds=0,
                enabled=True,
            )
        ]
    )

    issues = _checker(tmp_path).check_all(APIConfig(), SystemConfig(), mcp, MemoryConfig(), AgentConfig())

    assert any(issue.level == HealthLevel.ERROR and issue.code == "mcp_request_timeout_invalid" for issue in issues)


def test_config_health_flags_enabled_memory_without_embedding_model(tmp_path):
    memory = MemoryConfig(enabled=True, embedding_model_path="")

    issues = _checker(tmp_path).check_all(APIConfig(), SystemConfig(), MCPConfig(), memory, AgentConfig())

    assert any(issue.level == HealthLevel.ERROR and issue.code == "embedding_model_missing" for issue in issues)


def test_config_health_flags_invalid_tts_worker_limit(tmp_path):
    agent = AgentConfig()
    agent.tts_runtime.max_tts_workers = 0

    issues = _checker(tmp_path).check_all(APIConfig(), SystemConfig(), MCPConfig(), MemoryConfig(), agent)

    assert any(issue.level == HealthLevel.ERROR and issue.code == "tts_worker_limit_invalid" for issue in issues)


def test_config_health_flags_empty_log_root(tmp_path):
    system = SystemConfig()
    system.logging.log_root = "  "

    issues = _checker(tmp_path).check_all(APIConfig(), system, MCPConfig(), MemoryConfig(), AgentConfig())

    assert any(issue.level == HealthLevel.ERROR and issue.code == "log_root_empty" for issue in issues)


def test_config_health_flags_non_explicit_vision(tmp_path):
    system = SystemConfig()
    system.vision = VisionConfig.model_construct(enabled=True, explicit_trigger_only=False)

    issues = _checker(tmp_path).check_all(APIConfig(), system, MCPConfig(), MemoryConfig(), AgentConfig())

    assert any(issue.level == HealthLevel.ERROR and issue.code == "vision_must_be_explicit" for issue in issues)


def test_config_health_output_is_non_sensitive(tmp_path):
    private_root = tmp_path / "private" / "models"
    private_server_path = tmp_path / "private" / "server.py"
    api = APIConfig()
    api.llm.api_key = "fake-api-key"
    api.llm.base_url = "http://user:pass@127.0.0.1:8000/v1"
    api.asr.engine = "faster_whisper"
    api.asr.model_path = str(private_root / "missing-model")
    mcp = MCPConfig(
        servers=[
            MCPServerConfig(
                name=f"http://user:pass@127.0.0.1:9000/{private_server_path}",
                transport="sse",
                url="http://user:pass@127.0.0.1:9000/mcp",
                request_timeout_seconds=0,
                enabled=True,
            )
        ]
    )

    issues = _checker(tmp_path).check_all(api, SystemConfig(), mcp, MemoryConfig(), AgentConfig())
    text = _issue_text(issues)

    assert "fake-api-key" not in text
    assert "user:pass" not in text
    assert str(private_root) not in text
    assert str(private_server_path) not in text
    assert "missing-model" in text
