# 开发流程

## 环境

- Python: `E:/Tool/Miniconda/envs/ai/python.exe`
- 前端 / Tauri：`Set-Location apps/desktop; npm install; npm test; npm run dev`
- Rust shell：`Set-Location apps/desktop/src-tauri; cargo test`
- Python core：`python -m pytest tests/ -q`

## 当前阶段

- Tauri UI 迁移已完成，历史 PySide6 主线已退场。
- 当前主线是 Tauri / Vue / `python_core`。
- 后续工作优先维持 RPC contract、capability、发布安全、性能预算和文档 stale gate 的长期通过。
- 真实浏览器、OCR、MCP、STT / TTS / API 实机验收属于后续维护和 1.0 风险收口，不再作为 PySide6 退场前置条件。

## 1.0 验收门

进入 1.0 完成状态前，必须同时满足：

- 自动化测试通过，至少覆盖当前聚焦回归入口和受影响模块。
- API、TTS、STT、OCR、MCP、Playwright Edge 的实机矩阵通过，并记录结果。
- 诊断包人工抽查通过，确认无 API key、私有 URL 凭据、截图原图、音频、本地模型完整路径或长 OCR 原文泄露。
- 干净 Windows 环境可完成安装、启动和基础聊天链路运行。
- 文档入口、配置说明、故障排查说明和插件说明没有过期入口或误导性状态。
- 未完成项全部分类为 `post-1.0`、`maintenance` 或 `won't do`。

## 配置与数据

- `data/config/api.yaml`、`data/config/memory.yaml`、`data/config/mcp.yaml`、`data/config/system_config.yaml`、`data/config/agent.yaml` 均视为本地敏感或运行期配置。
- 本地模型、日志、浏览器会话、OCR 截图和记忆数据库默认不应提交。

## 配置化要求

- 关键体验参数不应长期硬编码在实现中。
- 现有高频参数优先进入配置层，再决定是否暴露到 UI。
- 迁移后新增参数必须先明确是示例值、默认值还是候选配置项。

## 测试策略

- 单元测试优先用 pytest。
- Python core 相关改动优先跑聚焦回归，再视影响扩大到全量 `tests/ -q`。
- 发布安全 / 性能 gate 基础入口：
  - `python scripts/check_docs_no_stale_ui_status.py`
  - `python scripts/check_no_pyside6_in_sidecar.py`
  - `python scripts/check_no_stdout_in_sidecar.py`
  - `python scripts/check_release_manifest.py --bundle apps/desktop/src-tauri/target/release/bundle`
  - `python scripts/check_release_forbidden_content.py --bundle apps/desktop/src-tauri/target/release/bundle`
  - `python scripts/check_release_reproducibility.py --bundle apps/desktop/src-tauri/target/release/bundle`
  - `python scripts/check_final_capabilities_match_build.py --bundle apps/desktop/src-tauri/target/release/bundle`
  - `python scripts/check_perf_budgets.py`

## 当前关注点

- Tauri 前端的设置、聊天、日志、工具和诊断页面行为一致性。
- Python sidecar 的 stdout 纪律、stderr 脱敏和任务状态机。
- capability / command / permission / schema 的一致性。
- 发布包、安装包和性能预算的长期 gate。
- 旧 Qt / PySide6 仅作为历史迁移归档，不再进入主线开发流程。
