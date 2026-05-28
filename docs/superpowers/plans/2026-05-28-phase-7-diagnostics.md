# Phase 7 诊断能力实施计划

> **给 agent 执行者：** 实施本计划时必须使用 `superpowers:subagent-driven-development`（推荐）或 `superpowers:executing-plans`，并按任务逐项执行。步骤使用 checkbox（`- [ ]`）语法追踪。

**目标：** 建立 Phase 7 诊断底座：可串联的平台日志、脱敏诊断包导出、配置健康检查、工具调用审计事件、第一版诊断运行器 / UI 入口，以及聊天窗最小失败恢复。

**架构：** 延展现有 `LogEvent` / `LogService` 链路，而不是另起一套观测系统。新增聚焦的核心模块处理诊断包、配置健康和 smoke check 编排，并通过现有设置中心与平台日志页暴露结果。所有真实设备检查保持可选且手动触发，核心 API 必须可 mock，方便离线测试。

**技术栈：** Python、PySide6、Pydantic、pytest、JSONL、zipfile，以及现有 `LogService`、`ToolRegistry`、`ConfigManager`、`SettingsWindow`、`ChatWindow`。

---

## 范围边界

本计划只覆盖 Phase 7 切片：

- 范围内：
  - 日志事件增加 `trace_id` / `request_id` / `stage` 字段
  - 脱敏诊断包导出
  - 第一版配置健康检查
  - 第一版工具执行审计明细
  - 第一版诊断运行器和设置页入口
  - 聊天窗最小失败恢复打磨
  - 相关文档更新
- 范围外：
  - 真正流式 STT
  - 自动工具回放
  - 自动配置修复
  - 后台持续看屏
  - 插件 marketplace 或签名体系
  - Phase 8 记忆账本和 Phase 9 Computer Use / 桌面应用自动化规划器

仓库级规则要求非用户明确确认时不创建提交。因此本计划使用验证检查点，不包含自动提交步骤。

## 文件结构

新增：

- `core/diagnostic_bundle.py`
  - 基于脱敏日志事件和非敏感运行摘要生成 zip 诊断包。
- `core/config_health.py`
  - 为 API、系统、MCP、记忆和 Agent 配置生成 warning / error / info 检查结果。
- `core/diagnostic_runner.py`
  - 运行手动触发的 smoke check，返回结构化结果；真实设备检查不作为 pytest 硬依赖。
- `ui/settings/pages/diagnostics_page.py`
  - 展示健康检查、手动 smoke check 操作、结果和导出入口。
- `tests/test_diagnostic_bundle.py`
  - 覆盖诊断包内容与脱敏。
- `tests/test_config_health.py`
  - 覆盖配置健康规则和敏感输出边界。
- `tests/test_diagnostic_runner.py`
  - 覆盖 fake check 的成功、失败与异常分类；若实现 timeout 分类，应同步补测试。
- `tests/test_diagnostics_page.py`
  - 覆盖页面构建、结果渲染和导出动作接线。

修改：

- `core/log_types.py`
  - 为 `LogEvent` 和 `build_log_event` 增加 trace 字段。
- `core/log_service.py`
  - 增加 trace / stage 查询过滤，并提供诊断包导出辅助入口。
- `core/log_sanitizer.py`
  - 强化脱敏，并增加有界文本、路径和 URL 摘要辅助函数。
- `core/tool_registry.py`
  - 增加 `tool.call_started`、更完整的审计明细、安全参数摘要和一致的来源元数据。
- `ui/settings/pages/system_log_page.py`
  - 增加诊断导出按钮、trace 感知详情渲染和工具审计分组优化。
- `ui/settings/window.py`
  - 在设置中心增加诊断页，并传入 `ConfigManager` 与 `LogService`。
- `ui/chat/window.py`
  - 收紧最小失败恢复：保留失败输入、保持重试 / 日志控件一致，并为请求失败日志附加 trace 元数据。
- `docs/README.md`
  - 如果文档索引保留 active plan 入口，则增加 Phase 7 计划引用。
- `docs/development.md`
  - 增加 Phase 7 诊断验证命令和手工 smoke 矩阵说明。
- `docs/superpowers/brainstorms/2026-05-28-future-stage-brainstorm.md`
  - 在 Phase 7 推荐处增加指向本计划的简短入口。
- `CLAUDE.md`
  - 如果本计划仍处于 active 状态，则在文档入口中增加链接。

## 任务 1：为日志事件增加 Trace 字段

**涉及文件：**

- 修改：`core/log_types.py`
- 修改：`core/log_service.py`
- 测试：`tests/test_log_service.py`
- 测试：`tests/test_logging_integration.py`

- [ ] **步骤 1：增加 trace 元数据序列化失败测试**

先更新 `tests/test_log_service.py` 的导入，加入 `build_log_event`：

```python
from core.log_types import LogChannel, LogEvent, LogLevel, build_log_event
```

追加到 `tests/test_log_service.py`：

```python
def test_log_event_serializes_trace_fields(tmp_path):
    service = LogService(log_root=tmp_path, system_flush_interval_ms=0)
    event = LogEvent(
        id="evt-trace",
        timestamp=datetime(2026, 5, 28, 9, 0, 0),
        channel=LogChannel.SYSTEM,
        level=LogLevel.INFO,
        source="llm.manager",
        event_type="llm.stream_started",
        session_id="session-1",
        utterance_id=7,
        summary="开始生成",
        details={},
        trace_id="trace-1",
        request_id="request-1",
        stage="llm",
    )

    service.record(event)

    data = service.query_events()[0]
    assert data["trace_id"] == "trace-1"
    assert data["request_id"] == "request-1"
    assert data["stage"] == "llm"
```

- [ ] **步骤 2：增加 trace 过滤失败测试**

追加到 `tests/test_log_service.py`：

```python
def test_log_service_filters_by_trace_request_and_stage(tmp_path):
    service = LogService(log_root=tmp_path, system_flush_interval_ms=0)
    service.record(
        build_log_event(
            channel=LogChannel.SYSTEM,
            level=LogLevel.INFO,
            source="chat.stt",
            event_type="stt.started",
            session_id="session-1",
            summary="stt",
            details={},
            trace_id="trace-1",
            request_id="request-1",
            stage="stt",
        )
    )
    service.record(
        build_log_event(
            channel=LogChannel.SYSTEM,
            level=LogLevel.INFO,
            source="chat.tts",
            event_type="tts.started",
            session_id="session-1",
            summary="tts",
            details={},
            trace_id="trace-2",
            request_id="request-2",
            stage="tts",
        )
    )

    assert [event["event_type"] for event in service.query_events(trace_id="trace-1")] == ["stt.started"]
    assert [event["event_type"] for event in service.query_events(request_id="request-2")] == ["tts.started"]
    assert [event["event_type"] for event in service.query_events(stage="stt")] == ["stt.started"]
```

- [ ] **步骤 3：运行聚焦失败测试**

运行：

```powershell
python -m pytest tests/test_log_service.py -q
```

实现前预期：出现 unexpected keyword `trace_id` 或缺少查询过滤参数相关失败。

- [ ] **步骤 4：实现 trace 字段**

更新 `core/log_types.py`：

```python
@dataclass(frozen=True)
class LogEvent:
    id: str
    timestamp: datetime
    channel: LogChannel
    level: LogLevel
    source: str
    event_type: str
    session_id: str
    utterance_id: int | None
    summary: str
    details: dict[str, Any]
    sensitive: bool = False
    trace_id: str = ""
    request_id: str = ""
    stage: str = ""
```

更新 `build_log_event` 签名和构造逻辑：

```python
def build_log_event(
    channel: LogChannel,
    level: LogLevel,
    source: str,
    event_type: str,
    session_id: str,
    summary: str,
    details: dict[str, Any] | None = None,
    utterance_id: int | None = None,
    sensitive: bool = False,
    trace_id: str = "",
    request_id: str = "",
    stage: str = "",
) -> LogEvent:
    return LogEvent(
        id=uuid4().hex,
        timestamp=datetime.now(),
        channel=channel,
        level=level,
        source=source,
        event_type=event_type,
        session_id=session_id,
        utterance_id=utterance_id,
        summary=summary,
        details=details or {},
        sensitive=sensitive,
        trace_id=trace_id,
        request_id=request_id,
        stage=stage,
    )
```

- [ ] **步骤 5：增加查询过滤器**

更新 `LogService.query_events`：

```python
def query_events(
    self,
    channel=None,
    source=None,
    session_id=None,
    trace_id=None,
    request_id=None,
    stage=None,
) -> list[dict]:
    events = self._events
    if channel is not None:
        channel_value = channel.value if isinstance(channel, LogChannel) else str(channel)
        events = [event for event in events if event.channel.value == channel_value]
    if source is not None:
        events = [event for event in events if event.source == source]
    if session_id is not None:
        events = [event for event in events if event.session_id == session_id]
    if trace_id is not None:
        events = [event for event in events if event.trace_id == trace_id]
    if request_id is not None:
        events = [event for event in events if event.request_id == request_id]
    if stage is not None:
        events = [event for event in events if event.stage == stage]
    return [event.to_json_dict() for event in events]
```

更新 `LogService.export_events`，接收并传递这些过滤参数：

```python
def export_events(
    self,
    path: Path | str,
    channel=None,
    source=None,
    session_id=None,
    trace_id=None,
    request_id=None,
    stage=None,
) -> None:
    export_path = Path(path)
    export_path.parent.mkdir(parents=True, exist_ok=True)
    events = self.query_events(
        channel=channel,
        source=source,
        session_id=session_id,
        trace_id=trace_id,
        request_id=request_id,
        stage=stage,
    )
    with export_path.open("w", encoding="utf-8") as fh:
        for event in events:
            fh.write(json.dumps(event, ensure_ascii=False) + "\n")
```

- [ ] **步骤 6：运行聚焦测试**

运行：

```powershell
python -m pytest tests/test_log_service.py tests/test_logging_integration.py -q
```

预期：选定测试全部通过。

## 任务 2：强化脱敏并导出诊断包

**涉及文件：**

- 新增：`core/diagnostic_bundle.py`
- 修改：`core/log_sanitizer.py`
- 修改：`core/log_service.py`
- 测试：`tests/test_log_sanitizer.py`
- 测试：`tests/test_diagnostic_bundle.py`

- [ ] **步骤 1：增加脱敏失败测试**

追加到 `tests/test_log_sanitizer.py`：

```python
def test_sanitize_details_masks_private_urls_and_long_paths():
    payload = {
        "api_url": "http://user:pass@127.0.0.1:9880/tts",
        "model_path": "E:/private/models/faster-whisper-large-v3-turbo",
        "screenshot_path": "data/vision/screen.png",
        "text": "短文本",
    }

    sanitized = sanitize_details(payload)

    assert sanitized["api_url"] == "http://***@127.0.0.1:9880/tts"
    assert sanitized["model_path"].endswith("faster-whisper-large-v3-turbo")
    assert sanitized["model_path"].startswith("***")
    assert sanitized["screenshot_path"].endswith("screen.png")
    assert sanitized["text"] == "短文本"
```

继续追加：

```python
def test_sanitize_details_truncates_large_text_fields():
    payload = {"ocr_text": "屏幕文字" * 500}

    sanitized = sanitize_details(payload)

    assert len(sanitized["ocr_text"]) < len(payload["ocr_text"])
    assert sanitized["ocr_text"].endswith("...<truncated>")
```

- [ ] **步骤 2：增加诊断包失败测试**

新增 `tests/test_diagnostic_bundle.py`：

```python
import json
import zipfile

from core.diagnostic_bundle import DiagnosticBundleExporter
from core.log_service import LogService


def test_diagnostic_bundle_exports_sanitized_logs_and_metadata(tmp_path):
    service = LogService(tmp_path / "logs", system_flush_interval_ms=0)
    service.record_system(
        "llm.manager",
        "llm.request_failed",
        "请求失败",
        {
            "api_key": "fake-api-key",
            "api_url": "http://user:pass@127.0.0.1:8000/v1",
            "text": "错误摘要",
        },
        session_id="session-1",
    )
    bundle_path = tmp_path / "diagnostic.zip"

    result = DiagnosticBundleExporter(service).export(bundle_path)

    assert result.path == bundle_path
    assert result.event_count == 1
    with zipfile.ZipFile(bundle_path) as archive:
        names = set(archive.namelist())
        assert names == {"metadata.json", "events.jsonl"}
        metadata = json.loads(archive.read("metadata.json").decode("utf-8"))
        events_text = archive.read("events.jsonl").decode("utf-8")

    assert metadata["format_version"] == 1
    assert "python_version" in metadata
    assert "fake-api-key" not in events_text
    assert "user:pass" not in events_text
    assert "llm.request_failed" in events_text
```

- [ ] **步骤 3：运行测试确认失败**

运行：

```powershell
python -m pytest tests/test_log_sanitizer.py tests/test_diagnostic_bundle.py -q
```

实现前预期：脱敏断言失败，且 `core.diagnostic_bundle` 导入失败。

- [ ] **步骤 4：实现有界脱敏辅助函数**

更新 `core/log_sanitizer.py`：

```python
from __future__ import annotations

from pathlib import Path
from urllib.parse import urlsplit, urlunsplit


SENSITIVE_KEYS = {"api_key", "token", "password", "authorization", "cookie"}
PATH_KEYS = {"model_path", "screenshot_path", "ref_audio_path", "log_root", "storage_dir"}
URL_KEYS = {"api_url", "base_url", "url"}
LONG_TEXT_KEYS = {"ocr_text", "page_text", "prompt_text", "text"}
MAX_TEXT_CHARS = 800


def _mask_url(value: str) -> str:
    try:
        parts = urlsplit(value)
    except ValueError:
        return value
    if "@" not in parts.netloc:
        return value
    host = parts.netloc.split("@", 1)[1]
    return urlunsplit((parts.scheme, f"***@{host}", parts.path, parts.query, parts.fragment))


def _summarize_path(value: str) -> str:
    if not value:
        return value
    name = Path(value).name
    if not name or name == value:
        return value
    return f"***/{name}"


def _truncate_text(value: str) -> str:
    if len(value) <= MAX_TEXT_CHARS:
        return value
    return value[:MAX_TEXT_CHARS] + "...<truncated>"


def sanitize_details(value, key_hint: str = ""):
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            normalized = key.lower()
            if normalized in SENSITIVE_KEYS:
                result[key] = "***"
                continue
            result[key] = sanitize_details(item, normalized)
        return result
    if isinstance(value, list):
        return [sanitize_details(item, key_hint) for item in value]
    if isinstance(value, str):
        if key_hint in URL_KEYS:
            return _mask_url(value)
        if key_hint in PATH_KEYS:
            return _summarize_path(value)
        if key_hint in LONG_TEXT_KEYS:
            return _truncate_text(value)
    return value
```

- [ ] **步骤 5：实现诊断包导出器**

新增 `core/diagnostic_bundle.py`：

```python
from __future__ import annotations

from dataclasses import dataclass
import json
import platform
from pathlib import Path
import sys
import zipfile

from core.log_service import LogService
from core.log_sanitizer import sanitize_details


@dataclass(frozen=True)
class DiagnosticBundleResult:
    path: Path
    event_count: int


class DiagnosticBundleExporter:
    def __init__(self, log_service: LogService):
        self._log_service = log_service

    def export(self, path: Path | str) -> DiagnosticBundleResult:
        bundle_path = Path(path)
        bundle_path.parent.mkdir(parents=True, exist_ok=True)
        events = self._log_service.query_events()
        metadata = {
            "format_version": 1,
            "platform": platform.platform(),
            "python_version": sys.version.split()[0],
            "event_count": len(events),
        }
        with zipfile.ZipFile(bundle_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("metadata.json", json.dumps(metadata, ensure_ascii=False, indent=2))
            lines = [
                json.dumps(sanitize_details(event), ensure_ascii=False)
                for event in events
            ]
            archive.writestr("events.jsonl", "\n".join(lines) + ("\n" if lines else ""))
        return DiagnosticBundleResult(path=bundle_path, event_count=len(events))
```

- [ ] **步骤 6：增加 LogService 便捷方法**

追加到 `core/log_service.py`：

```python
    def export_diagnostic_bundle(self, path: Path | str):
        from core.diagnostic_bundle import DiagnosticBundleExporter

        return DiagnosticBundleExporter(self).export(path)
```

- [ ] **步骤 7：运行聚焦测试**

运行：

```powershell
python -m pytest tests/test_log_sanitizer.py tests/test_diagnostic_bundle.py tests/test_log_service.py -q
```

预期：选定测试全部通过。

## 任务 3：增加配置健康检查

**涉及文件：**

- 新增：`core/config_health.py`
- 测试：`tests/test_config_health.py`
- 修改：`docs/development.md`

- [ ] **步骤 1：增加配置健康失败测试**

新增 `tests/test_config_health.py`：

```python
from config.schema import AgentConfig, APIConfig, MCPConfig, MCPServerConfig, MemoryConfig, SystemConfig
from core.config_health import ConfigHealthChecker, HealthLevel


def _checker(project_root):
    return ConfigHealthChecker(project_root=project_root)


def test_config_health_flags_missing_stt_model_path(tmp_path):
    api = APIConfig()
    api.asr.engine = "faster_whisper"
    api.asr.model_path = "missing/stt-model"

    issues = _checker(tmp_path).check_all(api, SystemConfig(), MCPConfig(), MemoryConfig(), AgentConfig())

    assert any(issue.level == HealthLevel.ERROR and issue.code == "asr_model_missing" for issue in issues)


def test_config_health_warns_about_non_baseline_tts_mode(tmp_path):
    api = APIConfig()
    api.tts.engine = "gptsovits"
    api.tts.audio_mode = "pcm_stream"
    api.tts.reference_mode = "auto"

    issues = _checker(tmp_path).check_all(api, SystemConfig(), MCPConfig(), MemoryConfig(), AgentConfig())

    assert any(issue.level == HealthLevel.WARN and issue.code == "tts_experimental_mode" for issue in issues)


def test_config_health_flags_enabled_mcp_without_command_or_url(tmp_path):
    mcp = MCPConfig(servers=[MCPServerConfig(name="broken", transport="stdio", command="", enabled=True)])

    issues = _checker(tmp_path).check_all(APIConfig(), SystemConfig(), mcp, MemoryConfig(), AgentConfig())

    assert any(issue.level == HealthLevel.ERROR and issue.code == "mcp_stdio_command_missing" for issue in issues)


def test_config_health_output_is_non_sensitive(tmp_path):
    api = APIConfig()
    setattr(api.llm, "api_key", "fake-api-key")
    api.llm.base_url = "http://user:pass@127.0.0.1:8000/v1"

    issues = _checker(tmp_path).check_all(api, SystemConfig(), MCPConfig(), MemoryConfig(), AgentConfig())
    text = "\n".join(issue.message for issue in issues)

    assert "fake-api-key" not in text
    assert "user:pass" not in text
```

- [ ] **步骤 2：运行测试确认模块缺失**

运行：

```powershell
python -m pytest tests/test_config_health.py -q
```

实现前预期：`core.config_health` 导入失败。

- [ ] **步骤 3：实现健康检查器**

新增 `core/config_health.py`：

```python
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

    def _resolve(self, value: str) -> Path:
        path = Path(value)
        if path.is_absolute():
            return path
        return self._project_root / path

    def _check_api(self, api: APIConfig) -> list[ConfigHealthIssue]:
        issues: list[ConfigHealthIssue] = []
        if api.asr.engine == "faster_whisper" and not self._resolve(api.asr.model_path).exists():
            issues.append(ConfigHealthIssue(
                HealthLevel.ERROR,
                "api.asr",
                "asr_model_missing",
                "语音识别模型目录不存在，请在 API 设置中选择有效的 faster-whisper 模型目录。",
                {"model_dir_name": Path(api.asr.model_path).name},
            ))
        if api.tts.engine == "gptsovits" and not (
            api.tts.audio_mode == "wav" and api.tts.reference_mode == "inline"
        ):
            issues.append(ConfigHealthIssue(
                HealthLevel.WARN,
                "api.tts",
                "tts_experimental_mode",
                "`wav + inline` 是当前稳定保底组合；当前 TTS 模式属于扩展或实验路径。",
                {"audio_mode": api.tts.audio_mode, "reference_mode": api.tts.reference_mode},
            ))
        return issues

    def _check_system(self, system: SystemConfig) -> list[ConfigHealthIssue]:
        issues: list[ConfigHealthIssue] = []
        if not system.logging.log_root.strip():
            issues.append(ConfigHealthIssue(
                HealthLevel.ERROR,
                "system.logging",
                "log_root_empty",
                "日志目录为空，平台日志和诊断包无法可靠落盘。",
            ))
        if system.vision.enabled and not system.vision.explicit_trigger_only:
            issues.append(ConfigHealthIssue(
                HealthLevel.ERROR,
                "system.vision",
                "vision_must_be_explicit",
                "视觉输入必须保持显式触发，不能开启后台自动读屏。",
            ))
        return issues

    def _check_mcp(self, mcp: MCPConfig) -> list[ConfigHealthIssue]:
        issues: list[ConfigHealthIssue] = []
        for server in mcp.servers:
            if not server.enabled:
                continue
            if server.transport == "stdio" and not server.command.strip():
                issues.append(ConfigHealthIssue(
                    HealthLevel.ERROR,
                    "mcp",
                    "mcp_stdio_command_missing",
                    f"MCP 服务器 {server.name or '<未命名>'} 启用 stdio transport 但命令为空。",
                ))
            if server.transport in {"sse", "http"} and not server.url.strip():
                issues.append(ConfigHealthIssue(
                    HealthLevel.ERROR,
                    "mcp",
                    "mcp_url_missing",
                    f"MCP 服务器 {server.name or '<未命名>'} 启用网络 transport 但 URL 为空。",
                ))
            if server.request_timeout_seconds <= 0:
                issues.append(ConfigHealthIssue(
                    HealthLevel.ERROR,
                    "mcp",
                    "mcp_request_timeout_invalid",
                    f"MCP 服务器 {server.name or '<未命名>'} 请求超时必须大于 0 秒。",
                ))
        return issues

    def _check_memory(self, memory: MemoryConfig) -> list[ConfigHealthIssue]:
        if memory.enabled and not memory.embedding_model_path.strip():
            return [ConfigHealthIssue(
                HealthLevel.ERROR,
                "memory",
                "embedding_model_missing",
                "启用记忆前必须选择本地向量模型目录。",
            )]
        return []

    def _check_agent(self, agent: AgentConfig) -> list[ConfigHealthIssue]:
        if agent.tts_runtime.max_tts_workers < 1:
            return [ConfigHealthIssue(
                HealthLevel.ERROR,
                "agent.tts_runtime",
                "tts_worker_limit_invalid",
                "TTS 合成 worker 上限必须至少为 1。",
            )]
        return []
```

- [ ] **步骤 4：运行聚焦测试**

运行：

```powershell
python -m pytest tests/test_config_health.py tests/test_config.py -q
```

预期：选定测试全部通过。

## 任务 4：增加工具执行审计事件

**涉及文件：**

- 修改：`core/tool_registry.py`
- 修改：`ui/settings/pages/system_log_page.py`
- 测试：`tests/test_tool_registry.py`
- 测试：`tests/test_system_log_page.py`

- [ ] **步骤 1：增加工具审计失败测试**

追加到 `tests/test_tool_registry.py`：

```python
def test_tool_registry_records_started_and_completed_audit_events(tmp_path):
    class FakeLogService:
        def __init__(self):
            self.events = []

        def record(self, event):
            self.events.append(event)

    plugin_host = PluginHost(tmp_path / "plugins")
    plugin_host.plugins = [DemoPlugin()]
    log_service = FakeLogService()
    registry = ToolRegistry(plugin_host=plugin_host, log_service=log_service)

    assert registry.call_tool("demo__echo", {"text": "hello"}) == "hello"

    event_types = [event.event_type for event in log_service.events]
    assert event_types == ["tool.call_started", "tool.call_completed"]
    completed = log_service.events[-1]
    assert completed.details["qualified_name"] == "demo__echo"
    assert completed.details["source_type"] == "plugin"
    assert completed.details["source_name"] == "demo"
    assert completed.details["arguments_summary"]["text"] == "hello"
    assert "result_preview" in completed.details
```

继续追加：

```python
def test_tool_registry_audit_summarizes_long_arguments(tmp_path):
    class FakeLogService:
        def __init__(self):
            self.events = []

        def record(self, event):
            self.events.append(event)

    plugin_host = PluginHost(tmp_path / "plugins")
    plugin_host.plugins = [DemoPlugin()]
    registry = ToolRegistry(plugin_host=plugin_host, log_service=FakeLogService())
    long_text = "x" * 1200

    registry.call_tool("demo__echo", {"text": long_text})

    summary = registry._log_service.events[-1].details["arguments_summary"]["text"]
    assert len(summary) < len(long_text)
    assert summary.endswith("...<truncated>")
```

- [ ] **步骤 2：运行失败测试**

运行：

```powershell
python -m pytest tests/test_tool_registry.py -q
```

实现前预期：审计事件顺序和摘要断言失败。

- [ ] **步骤 3：实现审计辅助函数**

更新 `core/tool_registry.py` 导入：

```python
from core.log_sanitizer import sanitize_details
```

为 `ToolRegistry` 增加辅助方法：

```python
    def _audit_details(
        self,
        qualified_name: str,
        arguments: dict[str, Any],
        started: float,
        result: Any = None,
        error: Exception | None = None,
    ) -> dict[str, Any]:
        entry = self._entry_for_tool(qualified_name)
        details = {
            "qualified_name": qualified_name,
            "tool_name": entry.name if entry else qualified_name,
            "source_type": entry.source if entry else "unknown",
            "source_name": entry.source_name if entry else "",
            "arguments_summary": sanitize_details(arguments),
            "elapsed_ms": int((time.perf_counter() - started) * 1000),
        }
        if result is not None:
            details["result_preview"] = str(result)[:200]
        if error is not None:
            details["error"] = str(error)
            details["error_type"] = type(error).__name__
        return details
```

在 `call_tool` 分发前记录 started 事件：

```python
        self._record_log_event(
            channel=LogChannel.SYSTEM,
            level=LogLevel.INFO,
            source=self._log_source_for_tool(qualified_name),
            event_type="tool.call_started",
            session_id=session_id,
            utterance_id=utterance_id,
            summary=f"{qualified_name} started",
            details=self._audit_details(qualified_name, arguments, started),
            stage="tool",
        )
```

替换 completed 明细：

```python
                    details=self._audit_details(qualified_name, arguments, started, result=result),
                    stage="tool",
```

替换 failed 明细：

```python
                    details=self._audit_details(qualified_name, arguments, started, error=exc),
                    stage="tool",
```

- [ ] **步骤 4：更新平台日志工具分组**

在 `ui/settings/pages/system_log_page.py` 中，让工具分组包含实际工具执行来源：

```python
    "工具": ["tool.registry", "plugin.*", "mcp.*"],
```

保留 `插件` 和 `MCP` 分组用于宿主诊断：

```python
    "插件": ["plugin.host", "plugin.*"],
    "MCP": ["mcp.host", "mcp.*"],
```

如果既有 `test_system_log_page_filters_plugin_and_mcp_prefix_sources` 只期望 plugin / mcp 事件出现在各自分组中，需同步更新。新增断言：选择 `工具` 时能同时看到 plugin 与 MCP 工具事件：

```python
    page._source_group_filter.setCurrentText("工具")
    page._refresh_view()
    assert page._event_list.count() == 2
```

同步更新既有 `test_tool_registry_records_plugin_and_mcp_specific_log_sources`。工具审计新增 `tool.call_started` 后，每次调用会产生 started / completed 两类事件；旧断言如果只期望两个来源，需要改为过滤 `tool.call_completed`：

```python
    completed_events = [
        event for event in log_service.events
        if event.event_type == "tool.call_completed"
    ]
    assert [event.source for event in completed_events] == ["plugin.demo", "mcp.notes"]
```

- [ ] **步骤 5：运行聚焦测试**

运行：

```powershell
python -m pytest tests/test_tool_registry.py tests/test_system_log_page.py -q
```

预期：选定测试全部通过。

## 任务 5：增加诊断运行器和设置页入口

**涉及文件：**

- 新增：`core/diagnostic_runner.py`
- 新增：`ui/settings/pages/diagnostics_page.py`
- 修改：`ui/settings/window.py`
- 测试：`tests/test_diagnostic_runner.py`
- 测试：`tests/test_diagnostics_page.py`
- 测试：`tests/test_settings_window.py`

- [ ] **步骤 1：增加诊断运行器测试**

新增 `tests/test_diagnostic_runner.py`：

```python
from core.diagnostic_runner import DiagnosticCheck, DiagnosticRunner, DiagnosticStatus


def test_diagnostic_runner_records_success_and_failure():
    runner = DiagnosticRunner([
        DiagnosticCheck("api", "API 连通", lambda: {"ok": True}),
        DiagnosticCheck("tts", "TTS", lambda: (_ for _ in ()).throw(RuntimeError("boom"))),
    ])

    results = runner.run_all()

    assert [result.key for result in results] == ["api", "tts"]
    assert results[0].status == DiagnosticStatus.PASS
    assert results[1].status == DiagnosticStatus.FAIL
    assert results[1].error_type == "RuntimeError"
    assert "boom" in results[1].message
```

- [ ] **步骤 2：增加诊断页测试**

新增 `tests/test_diagnostics_page.py`：

```python
from pathlib import Path

from PySide6.QtWidgets import QApplication

from config.schema import AgentConfig, APIConfig, MCPConfig, MemoryConfig, SystemConfig
from core.config_health import ConfigHealthIssue, HealthLevel
from core.diagnostic_runner import DiagnosticCheckResult, DiagnosticStatus
from ui.settings.pages.diagnostics_page import DiagnosticsPage


def _app():
    app = QApplication.instance()
    return app or QApplication([])


class _FakeConfig:
    def __init__(self):
        self.api = APIConfig()
        self.system = SystemConfig()
        self.mcp = MCPConfig()
        self.memory = MemoryConfig()
        self.agent = AgentConfig()


class _FakeLogService:
    log_root = Path(".")

    def export_diagnostic_bundle(self, path):
        self.exported_path = path
        return type("Result", (), {"path": path, "event_count": 0})()


def test_diagnostics_page_renders_health_and_smoke_results(monkeypatch):
    _app()
    page = DiagnosticsPage(_FakeConfig(), _FakeLogService())
    monkeypatch.setattr(
        page,
        "_collect_health_issues",
        lambda: [ConfigHealthIssue(HealthLevel.WARN, "api.tts", "tts_experimental_mode", "TTS 扩展模式")],
        raising=False,
    )
    monkeypatch.setattr(
        page,
        "_run_smoke_checks",
        lambda: [DiagnosticCheckResult("api", "API 连通", DiagnosticStatus.PASS, "通过", {}, "", 1)],
        raising=False,
    )

    page._refresh_health()
    page._run_checks()

    assert "TTS 扩展模式" in page._health_text.toPlainText()
    assert "API 连通" in page._result_text.toPlainText()
    assert "通过" in page._result_text.toPlainText()
```

- [ ] **步骤 3：运行测试确认模块缺失**

运行：

```powershell
python -m pytest tests/test_diagnostic_runner.py tests/test_diagnostics_page.py -q
```

实现前预期：导入失败。

- [ ] **步骤 4：实现诊断运行器**

新增 `core/diagnostic_runner.py`：

```python
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import time
from typing import Any, Callable


class DiagnosticStatus(str, Enum):
    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"


@dataclass(frozen=True)
class DiagnosticCheckResult:
    key: str
    label: str
    status: DiagnosticStatus
    message: str
    details: dict[str, Any] = field(default_factory=dict)
    error_type: str = ""
    elapsed_ms: int = 0


@dataclass(frozen=True)
class DiagnosticCheck:
    key: str
    label: str
    run: Callable[[], dict[str, Any] | None]


class DiagnosticRunner:
    def __init__(self, checks: list[DiagnosticCheck]):
        self._checks = checks

    def run_all(self) -> list[DiagnosticCheckResult]:
        return [self._run_check(check) for check in self._checks]

    def _run_check(self, check: DiagnosticCheck) -> DiagnosticCheckResult:
        started = time.perf_counter()
        try:
            details = check.run() or {}
            status = DiagnosticStatus.WARN if details.get("warning") else DiagnosticStatus.PASS
            message = str(details.get("message") or "通过")
            return DiagnosticCheckResult(
                key=check.key,
                label=check.label,
                status=status,
                message=message,
                details=details,
                elapsed_ms=int((time.perf_counter() - started) * 1000),
            )
        except Exception as exc:
            return DiagnosticCheckResult(
                key=check.key,
                label=check.label,
                status=DiagnosticStatus.FAIL,
                message=str(exc),
                error_type=type(exc).__name__,
                elapsed_ms=int((time.perf_counter() - started) * 1000),
            )
```

- [ ] **步骤 5：实现 DiagnosticsPage**

新增 `ui/settings/pages/diagnostics_page.py`：

```python
from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QFileDialog, QLabel, QPushButton, QTextEdit, QVBoxLayout, QWidget

from core.config_health import ConfigHealthChecker
from core.diagnostic_runner import DiagnosticCheck, DiagnosticRunner
from ui.theme import settings_page_title


class DiagnosticsPage(QWidget):
    def __init__(self, config, log_service, parent=None):
        super().__init__(parent)
        self._config = config
        self._log_service = log_service

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(12)
        layout.addWidget(settings_page_title(QLabel("诊断")))

        self._health_text = QTextEdit()
        self._health_text.setReadOnly(True)
        layout.addWidget(self._health_text, 2)

        self._result_text = QTextEdit()
        self._result_text.setReadOnly(True)
        layout.addWidget(self._result_text, 3)

        self._refresh_btn = QPushButton("刷新配置健康")
        self._refresh_btn.clicked.connect(self._refresh_health)
        layout.addWidget(self._refresh_btn)

        self._run_btn = QPushButton("运行本机诊断")
        self._run_btn.clicked.connect(self._run_checks)
        layout.addWidget(self._run_btn)

        self._export_btn = QPushButton("导出诊断包")
        self._export_btn.clicked.connect(self._export_bundle)
        layout.addWidget(self._export_btn)

        self._refresh_health()

    def _collect_health_issues(self):
        return ConfigHealthChecker().check_all(
            self._config.api,
            self._config.system,
            self._config.mcp,
            self._config.memory,
            self._config.agent,
        )

    def _run_smoke_checks(self):
        checks = [
            DiagnosticCheck("logs", "平台日志目录", lambda: {"message": str(self._log_service.log_root)}),
            DiagnosticCheck("config", "配置模型", lambda: {"message": "配置对象加载完成"}),
        ]
        return DiagnosticRunner(checks).run_all()

    def _refresh_health(self):
        issues = self._collect_health_issues()
        if not issues:
            self._health_text.setPlainText("配置健康检查未发现阻塞问题。")
            return
        lines = [f"[{issue.level.value.upper()}] {issue.area} {issue.code}: {issue.message}" for issue in issues]
        self._health_text.setPlainText("\n".join(lines))

    def _run_checks(self):
        results = self._run_smoke_checks()
        lines = [
            f"[{result.status.value.upper()}] {result.label}: {result.message} ({result.elapsed_ms}ms)"
            for result in results
        ]
        self._result_text.setPlainText("\n".join(lines))

    def _choose_bundle_path(self) -> Path | None:
        path, _ = QFileDialog.getSaveFileName(
            self,
            "导出诊断包",
            str(Path(self._log_service.log_root) / "yumetsuki-diagnostic.zip"),
            "Zip (*.zip)",
        )
        return Path(path) if path else None

    def _export_bundle(self):
        path = self._choose_bundle_path()
        if path is None:
            return
        result = self._log_service.export_diagnostic_bundle(path)
        self._result_text.setPlainText(f"诊断包已导出：{result.path}\n事件数量：{result.event_count}")
```

- [ ] **步骤 6：接入 SettingsWindow**

修改 `ui/settings/window.py`：

Add import:

```python
from ui.settings.pages.diagnostics_page import DiagnosticsPage
```

Add page after platform log page:

```python
        self._diagnostics_page = DiagnosticsPage(self._config, self._log_service)
        self._stack.addWidget(self._diagnostics_page)
```

更新导航标签和索引。保持 `API / 角色 / 记忆 / Agent / 插件 / MCP / 对话日志 / 平台日志 / 诊断 / 系统` 顺序：

```python
        pages_info = [
            ("🔑  API", 0),
            ("👤  角色", 1),
            ("🧠  记忆", 2),
            ("🤖  Agent", 5),
            ("🧩  插件", 6),
            ("🔌  MCP", 9),
            ("📝  对话日志", 3),
            ("🧪  平台日志", 4),
            ("🩺  诊断", 7),
            ("⚙  系统", 8),
        ]
```

按匹配的 stack 顺序创建页面：

```python
        self._conversation_log_page = ConversationLogPage(self._log_service)
        self._stack.addWidget(self._conversation_log_page)

        self._system_log_page = SystemLogPage(self._log_service)
        self._stack.addWidget(self._system_log_page)

        self._agent_page = AgentPage(self._config.agent, config=self._config)
        self._stack.addWidget(self._agent_page)

        self._plugin_page = PluginPage(config=self._config)
        self._stack.addWidget(self._plugin_page)

        self._diagnostics_page = DiagnosticsPage(self._config, self._log_service)
        self._stack.addWidget(self._diagnostics_page)

        self._system_page = SystemPage(self._config.system)
        self._stack.addWidget(self._system_page)

        self._mcp_page = MCPPage(config=self._config)
        self._stack.addWidget(self._mcp_page)
```

更新保存按钮可见性：

```python
        self._save_btn.setVisible(index in {0, 8})
```

更新保存分支，并把所有既有系统页索引检查从 `7` 改为 `8`，包括 `_switch_page()` reset 逻辑和 `_confirm_save()`：

```python
        if current_index == 8 and index != 8:
            self._system_page.reset()

        if index == 8:
            self._save_btn.setText("保存系统配置")

        elif current_index == 8:
            message = "确定保存当前系统设定吗？"
            save = self._apply_and_save_system
            success = "系统设定已成功保存。"
```

- [ ] **步骤 7：更新新增页面对应的设置页测试**

修改 `tests/test_settings_window.py` 的导航期望：

```python
    assert labels == [
        "🔑  API",
        "👤  角色",
        "🧠  记忆",
        "🤖  Agent",
        "🧩  插件",
        "🔌  MCP",
        "📝  对话日志",
        "🧪  平台日志",
        "🩺  诊断",
        "⚙  系统",
    ]
```

更新期望目标：

```python
    expected_targets = {
        "🔑  API": 0,
        "👤  角色": 1,
        "🧠  记忆": 2,
        "🤖  Agent": 5,
        "🧩  插件": 6,
        "🔌  MCP": 9,
        "📝  对话日志": 3,
        "🧪  平台日志": 4,
        "🩺  诊断": 7,
        "⚙  系统": 8,
    }
```

把切换到系统页的测试从索引 `7` 改为 `8`。

- [ ] **步骤 8：运行聚焦 UI 测试**

运行：

```powershell
python -m pytest tests/test_diagnostic_runner.py tests/test_diagnostics_page.py tests/test_settings_window.py -q
```

预期：选定测试全部通过。

## 任务 6：增加聊天窗最小失败恢复

**涉及文件：**

- 修改：`ui/chat/window.py`
- 测试：`tests/test_chat_stt_flow.py`
- 测试：`tests/test_chat_tts_flow.py`

- [ ] **步骤 1：增加失败输入保留和日志按钮目标测试**

追加到 `tests/test_chat_stt_flow.py`：

```python
def test_chat_failure_preserves_last_input_and_keeps_retry_and_log_controls(monkeypatch):
    window = _make_window(monkeypatch, patch_llm_worker=True)
    opened_pages = []
    monkeypatch.setattr(window, "_open_settings_page", lambda index: opened_pages.append(index), raising=False)
    try:
        window._last_user_input = "帮我总结这个页面"
        window._on_llm_error("timeout")

        assert "请求失败" in window._status_label.text()
        assert not window._retry_btn.isHidden()
        assert not window._logs_btn.isHidden()

        window._logs_btn.click()
        assert opened_pages == [4]

        window._retry_btn.click()
        assert _FakeLLMWorker.instances[-1].user_input == "帮我总结这个页面"
    finally:
        _close_window(window)
```

- [ ] **步骤 2：增加请求失败 trace 字段失败测试**

追加到 `tests/test_chat_stt_flow.py`：

```python
def test_chat_failure_log_includes_trace_stage(monkeypatch):
    log_service = _RecordingLogService()
    window = _make_window(monkeypatch, patch_llm_worker=True, log_service=log_service)
    try:
        window._last_user_input = "你好"
        window._on_llm_error("boom")

        event = next(event for event in log_service.events if event.event_type == "chat.request_failed")
        assert event.stage == "chat"
        assert event.trace_id
        assert event.request_id
    finally:
        _close_window(window)
```

- [ ] **步骤 3：运行失败测试**

运行：

```powershell
python -m pytest tests/test_chat_stt_flow.py -q
```

实现前预期：trace 字段为空，或重试 / 日志状态断言失败。

- [ ] **步骤 4：为 ChatWindow 增加 trace id 管理**

In `ui/chat/window.py`, import `uuid4`:

```python
from uuid import uuid4
```

In `ChatWindow.__init__`, add:

```python
        self._current_trace_id = ""
        self._current_request_id = ""
```

At the start of `_on_send`, after the final `text` is accepted:

```python
        self._current_trace_id = uuid4().hex
        self._current_request_id = uuid4().hex
```

Add a small helper so direct error-path tests and late failures still get trace metadata:

```python
    def _ensure_trace_ids(self) -> None:
        if not self._current_trace_id:
            self._current_trace_id = uuid4().hex
        if not self._current_request_id:
            self._current_request_id = uuid4().hex
```

更新 `_record_log_event` 包装方法，默认带上 trace 字段：

```python
    def _record_log_event(self, **kwargs) -> None:
        if self._log_service is None:
            return
        kwargs.setdefault("trace_id", self._current_trace_id)
        kwargs.setdefault("request_id", self._current_request_id)
        self._log_service.record(build_log_event(**kwargs))
```

- [ ] **步骤 5：收紧 `_on_llm_error` 恢复逻辑**

更新既有 `_on_llm_error`：

```python
    def _on_llm_error(self, message: str):
        self._ensure_trace_ids()
        error_message = str(message or "未知错误")
        if self._last_user_input:
            self._input.setText(self._last_user_input)
        self._set_chat_status(
            f"请求失败：{error_message}",
            error=True,
            can_retry=bool(self._last_user_input),
            show_logs=True,
        )
        self._record_log_event(
            channel=LogChannel.SYSTEM,
            level=LogLevel.ERROR,
            source="chat.window",
            event_type="chat.request_failed",
            session_id=self._tts_session_id,
            utterance_id=self._current_utterance_id,
            summary="聊天请求失败",
            details={"error": error_message},
            stage="chat",
        )
```

如果当前实现已经记录错误日志，保留既有 details，并补充 `_ensure_trace_ids()`、`stage="chat"` 和输入保留逻辑。

- [ ] **步骤 6：运行聚焦聊天测试**

运行：

```powershell
python -m pytest tests/test_chat_stt_flow.py tests/test_chat_tts_flow.py -q
```

预期：选定测试全部通过。

## 任务 7：文档与验证

**涉及文件：**

- 修改：`docs/development.md`
- 修改：`docs/superpowers/brainstorms/2026-05-28-future-stage-brainstorm.md`
- 修改：`docs/README.md`
- 修改：`CLAUDE.md`

- [ ] **步骤 1：更新开发文档验证命令**

添加到 `docs/development.md` 的 “Phase 7 实现后新增回归入口” 下，不要放进“当前可运行聚焦回归入口”：

```markdown
- Phase 7 诊断与审计：
  - `python -m pytest tests/test_log_sanitizer.py tests/test_log_service.py tests/test_diagnostic_bundle.py -q`
  - `python -m pytest tests/test_config_health.py tests/test_diagnostic_runner.py tests/test_diagnostics_page.py -q`
  - `python -m pytest tests/test_tool_registry.py tests/test_system_log_page.py tests/test_settings_window.py -q`
  - `python -m pytest tests/test_chat_stt_flow.py tests/test_chat_tts_flow.py -q`
```

- [ ] **步骤 2：更新头脑风暴文档**

在 `docs/superpowers/brainstorms/2026-05-28-future-stage-brainstorm.md` 顶部标记历史参考，并在 Phase 7 下使用相对 Markdown 链接指向本计划：

```markdown
实施计划：[Phase 7 诊断能力实施计划](../plans/2026-05-28-phase-7-diagnostics.md)
```

- [ ] **步骤 3：更新文档索引和 CLAUDE.md**

在 `docs/README.md` 和 `CLAUDE.md` 的文档入口区域增加 active plan 链接，并同步说明 brainstorm 文档位于 `docs/superpowers/brainstorms/`，属于历史参考：

```markdown
- [Phase 7 诊断能力实施计划](./superpowers/plans/2026-05-28-phase-7-diagnostics.md)
```

`CLAUDE.md` 使用：

```markdown
- [Phase 7 诊断能力实施计划](./docs/superpowers/plans/2026-05-28-phase-7-diagnostics.md)
```

- [ ] **步骤 4：运行文档和聚焦回归检查**

运行：

```powershell
python -m pytest tests/test_log_sanitizer.py tests/test_log_service.py tests/test_diagnostic_bundle.py -q
python -m pytest tests/test_config_health.py tests/test_diagnostic_runner.py tests/test_diagnostics_page.py -q
python -m pytest tests/test_tool_registry.py tests/test_system_log_page.py tests/test_settings_window.py -q
python -m pytest tests/test_chat_stt_flow.py tests/test_chat_tts_flow.py -q
```

预期：选定测试全部通过。

- [ ] **步骤 5：运行触达模块语法检查**

运行：

```powershell
python -m py_compile core/log_types.py core/log_service.py core/log_sanitizer.py core/diagnostic_bundle.py core/config_health.py core/diagnostic_runner.py core/tool_registry.py ui/settings/window.py ui/settings/pages/system_log_page.py ui/settings/pages/diagnostics_page.py ui/chat/window.py
```

预期：命令以退出码 0 结束。

## 最终手工 Smoke 矩阵

以下检查属于手工验收，不应成为 pytest 硬依赖：

- API:
  - 使用有效配置运行诊断页 API smoke check。
  - 使用缺失或无效 endpoint 运行一次，确认错误分类正确。
- TTS:
  - 确认 `wav + inline` 被标记为稳定基线。
  - 确认 `pcm_stream + auto` 被标记为扩展 / 实验路径。
- STT:
  - 在开发机录制一段短麦克风样本。
  - 确认超时和空结果路径仍可恢复。
- OCR:
  - 使用 RapidOCR 显式运行一次截图 OCR。
  - 确认不会发生后台持续截图。
- MCP:
  - 分别运行一个禁用 server、一个无效 stdio server 和一个 mock server。
  - 确认状态出现在诊断页和平台日志中。
- Browser:
  - 运行 Playwright Edge 可用性 smoke check。
  - 确认失败消息指向 `playwright install msedge`，但不会自动执行安装。
- 诊断包：
  - 导出诊断包。
  - 手工检查 zip，确认不包含 API key、截图原图、音频、私有 URL 凭据或完整模型路径。

## 自检清单

- 需求覆盖：
  - Trace 日志：任务 1。
  - 诊断包与脱敏：任务 2。
  - 配置健康：任务 3。
  - 工具审计：任务 4。
  - 诊断运行器和设置页 UI：任务 5。
  - 聊天失败恢复：任务 6。
  - 文档与验证：任务 7。
- 占位符扫描：
  - 本计划使用明确文件路径、代码片段、命令和预期结果。
- 类型一致性：
  - Trace 字段统一为 `trace_id`、`request_id` 和 `stage`。
  - 诊断状态统一为 `DiagnosticStatus.PASS`、`DiagnosticStatus.WARN` 和 `DiagnosticStatus.FAIL`。
  - 配置健康等级统一为 `HealthLevel.INFO`、`HealthLevel.WARN` 和 `HealthLevel.ERROR`。

## 收口与归档规则

- Phase 7 实现完成并被 `CLAUDE.md`、`docs/README.md` 和 `docs/development.md` 吸收后，本计划应归档或删除，避免长期作为 active plan 误导后续执行。
- 归档或删除本计划时，应同步清理 `CLAUDE.md`、`docs/README.md`、`docs/superpowers/brainstorms/2026-05-28-future-stage-brainstorm.md` 中的 active plan 入口，只保留必要的历史引用。

## 执行交接

计划已保存到 `docs/superpowers/plans/2026-05-28-phase-7-diagnostics.md`。有两种执行方式：

1. **Subagent-Driven（推荐）**：每个任务派发一个新的 subagent，任务之间做复审，迭代更快。
2. **Inline Execution（当前会话执行）**：在当前会话使用 `executing-plans` 执行，按批次设置检查点。

实现开始前需要先选择执行方式。
