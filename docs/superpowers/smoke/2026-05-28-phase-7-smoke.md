# Phase 7 实机验收待补记录

> 状态：Phase 7 已完成，本地自动化验证已通过；真实服务和本机设备验收待补。

## 已完成的本地验证

- `python -m pytest tests/ -q`
  - 结果：`519 passed`
- 触达模块语法检查已通过：
  - `core/log_types.py`
  - `core/log_service.py`
  - `core/log_sanitizer.py`
  - `core/diagnostic_bundle.py`
  - `core/config_health.py`
  - `core/diagnostic_runner.py`
  - `core/tool_registry.py`
  - `ui/settings/window.py`
  - `ui/settings/pages/system_log_page.py`
  - `ui/settings/pages/diagnostics_page.py`
  - `ui/chat/window.py`
  - `ui/theme.py`

## 待补实机验收矩阵

| 项目 | 状态 | 记录 |
|---|---|---|
| API 诊断 | 待补 | 使用有效配置和无效 endpoint 各运行一次诊断。 |
| TTS | 待补 | 确认 `wav + inline` 稳定基线，以及扩展模式提示。 |
| STT | 待补 | 使用真实麦克风和本地 faster-whisper 模型跑一次成功、空结果或超时路径。 |
| OCR | 待补 | 使用 RapidOCR 显式读屏一次，确认不会后台持续截图。 |
| MCP | 待补 | 覆盖禁用 server、无效 stdio server 和一个可用 mock/server。 |
| Browser | 待补 | 运行 Playwright Edge 可用性检查，失败时只提示安装，不自动执行安装。 |
| 诊断包 | 待补 | 导出 zip 并人工抽查，不应包含 API key、截图原图、音频、URL 凭据、完整模型路径或长 OCR 原文。 |

## 记录规则

- 只记录结果摘要、错误类型和可复现步骤。
- 不粘贴真实 API key、URL 凭据、本地私有路径全文、截图原图、音频或长 OCR 原文。
- 失败项保留为 `待修复` 或 `待复测`，不要用“理论上通过”替代实机结果。
