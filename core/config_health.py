from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from config.schema import AgentConfig, APIConfig, MCPConfig, MemoryConfig, SystemConfig


class HealthLevel(str, Enum):
    INFO = "info"
    WARN = "warn"
    ERROR = "error"


@dataclass(frozen=True)
class ConfigHealthIssue:
    level: HealthLevel
    area: str
    code: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)


class ConfigHealthChecker:
    def __init__(self, project_root: str | Path = "."):
        self._project_root = Path(project_root)

    def check_all(
        self,
        api: APIConfig,
        system: SystemConfig,
        mcp: MCPConfig,
        memory: MemoryConfig,
        agent: AgentConfig,
    ) -> list[ConfigHealthIssue]:
        issues: list[ConfigHealthIssue] = []
        issues.extend(self._check_api(api))
        issues.extend(self._check_system(system))
        issues.extend(self._check_mcp(mcp))
        issues.extend(self._check_memory(memory))
        issues.extend(self._check_agent(agent))
        return issues

    def _resolve_path(self, value: str) -> Path:
        path = Path(value)
        if path.is_absolute():
            return path
        return self._project_root / path

    def _check_api(self, api: APIConfig) -> list[ConfigHealthIssue]:
        issues: list[ConfigHealthIssue] = []
        asr_engine = str(api.asr.engine or "").strip().lower()
        model_path = str(api.asr.model_path or "").strip()
        if asr_engine == "faster_whisper" and (not model_path or not self._resolve_path(model_path).exists()):
            issues.append(
                ConfigHealthIssue(
                    level=HealthLevel.ERROR,
                    area="api.asr",
                    code="asr_model_missing",
                    message="语音识别模型目录不存在，请在 API 设置中选择有效的 faster-whisper 模型目录。",
                    details={"model_path": self._summarize_path(model_path)},
                )
            )

        tts_engine = str(api.tts.engine or "").strip().lower()
        audio_mode = str(api.tts.audio_mode or "").strip().lower()
        reference_mode = str(api.tts.reference_mode or "").strip().lower()
        if tts_engine == "gptsovits" and (audio_mode != "wav" or reference_mode != "inline"):
            issues.append(
                ConfigHealthIssue(
                    level=HealthLevel.WARN,
                    area="api.tts",
                    code="tts_experimental_mode",
                    message="当前 GPT-SoVITS TTS 模式属于扩展或实验路径；wav + inline 是稳定保底组合。",
                    details={
                        "audio_mode": audio_mode or "<空>",
                        "reference_mode": reference_mode or "<空>",
                    },
                )
            )
        return issues

    def _check_system(self, system: SystemConfig) -> list[ConfigHealthIssue]:
        issues: list[ConfigHealthIssue] = []
        if not str(system.logging.log_root or "").strip():
            issues.append(
                ConfigHealthIssue(
                    level=HealthLevel.ERROR,
                    area="system.logging",
                    code="log_root_empty",
                    message="日志目录为空，平台日志和诊断包无法可靠落盘。",
                )
            )
        if system.vision.enabled and not system.vision.explicit_trigger_only:
            issues.append(
                ConfigHealthIssue(
                    level=HealthLevel.ERROR,
                    area="system.vision",
                    code="vision_must_be_explicit",
                    message="视觉输入必须保持显式触发，不能开启后台自动读屏。",
                )
            )
        return issues

    def _check_mcp(self, mcp: MCPConfig) -> list[ConfigHealthIssue]:
        issues: list[ConfigHealthIssue] = []
        for index, server in enumerate(mcp.servers, start=1):
            if not server.enabled:
                continue

            transport = str(server.transport or "").strip().lower()
            server_label = f"#{index}"
            details = {"server": server_label, "transport": transport or "<空>"}

            if transport == "stdio" and not str(server.command or "").strip():
                issues.append(
                    ConfigHealthIssue(
                        level=HealthLevel.ERROR,
                        area="mcp",
                        code="mcp_stdio_command_missing",
                        message=f"MCP 服务器 {server_label} 启用 stdio transport 但命令为空。",
                        details=details,
                    )
                )
            if transport in {"sse", "http"} and not str(server.url or "").strip():
                issues.append(
                    ConfigHealthIssue(
                        level=HealthLevel.ERROR,
                        area="mcp",
                        code="mcp_url_missing",
                        message=f"MCP 服务器 {server_label} 启用网络 transport 但 URL 为空。",
                        details=details,
                    )
                )
            if server.request_timeout_seconds <= 0:
                issues.append(
                    ConfigHealthIssue(
                        level=HealthLevel.ERROR,
                        area="mcp",
                        code="mcp_request_timeout_invalid",
                        message=f"MCP 服务器 {server_label} 请求超时必须大于 0 秒。",
                        details={
                            "server": server_label,
                            "request_timeout_seconds": server.request_timeout_seconds,
                        },
                    )
                )
        return issues

    def _check_memory(self, memory: MemoryConfig) -> list[ConfigHealthIssue]:
        if memory.enabled and not str(memory.embedding_model_path or "").strip():
            return [
                ConfigHealthIssue(
                    level=HealthLevel.ERROR,
                    area="memory",
                    code="embedding_model_missing",
                    message="启用记忆前必须选择本地向量模型目录。",
                )
            ]
        return []

    def _check_agent(self, agent: AgentConfig) -> list[ConfigHealthIssue]:
        if agent.tts_runtime.max_tts_workers < 1:
            return [
                ConfigHealthIssue(
                    level=HealthLevel.ERROR,
                    area="agent.tts_runtime",
                    code="tts_worker_limit_invalid",
                    message="TTS 合成 worker 上限必须至少为 1。",
                    details={"max_tts_workers": agent.tts_runtime.max_tts_workers},
                )
            ]
        return []

    def _summarize_path(self, value: str) -> str:
        if not value:
            return "<空>"
        name = Path(value).name
        if not name or name == value:
            return name or "<空>"
        return f"***/{name}"
