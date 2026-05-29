# Yumetsuki

Yumetsuki（梦月）是一个桌宠 AI 伴侣项目，核心体验是角色演出、自然对话、本地配置可控，以及可扩展的工具、语音、记忆、MCP、浏览器自动化和 OCR 能力。

当前主 UI 已切到 Tauri/Vue + `python_core` headless sidecar；历史 PySide6 入口、旧 `ui/` 主实现和 PySide6 依赖已退场。

## 快速开始

Tauri 桌面工程命令：

- 前端开发页：在仓库根目录执行 `pnpm install`、`pnpm dev`
- 自动化验证：在仓库根目录执行 `pnpm test`、`pnpm e2e:smoke`
- Rust shell：在 `apps/desktop/src-tauri` 下执行 `cargo test`
- Python sidecar：执行 `python -m pytest tests/rpc_contract/ -q`
- 发布 gate 基础脚本：`python scripts/check_release_manifest.py --bundle apps/desktop/src-tauri/target/release/bundle`

## 可选能力准备

下列能力按需准备，缺失时不应阻塞基础聊天和设置中心：

- STT：在 `data/models/stt/` 放置 faster-whisper 模型目录，并在 API 设置中启用 ASR。
- TTS / LLM：在 API 设置中填写对应服务地址、模型和密钥；本地敏感配置不应提交。
- MCP：在 MCP 设置页新增 server，可配置 transport、命令或 URL、连接超时、请求超时和失败重试。
- Web 自动化：安装 Playwright 后执行 `playwright install msedge`，再按 `docs/plugin-web-automation.md` 配置权限。
- OCR：默认使用 RapidOCR；PaddleOCR 属于进阶可选后端，按 `docs/vision-ocr.md` 准备环境。

## 文档入口

- [文档总览](./docs/README.md)
- [代码架构](./docs/architecture.md)
- [UI 规范](./docs/ui-guidelines.md)
- [开发流程](./docs/development.md)
- [Tauri 桌面打包与发布安全](./docs/release/desktop-packaging.md)
- [插件与 MCP](./docs/plugin-mcp.md)
- [Web 自动化插件](./docs/plugin-web-automation.md)
- [系统控制插件](./docs/plugin-system-control.md)
- [OCR 与视觉输入](./docs/vision-ocr.md)
- [服务端 TTS 对接规范](./docs/service-tts-compatibility.md)

## 本地数据与敏感配置

`data/config/api.yaml`、`data/config/memory.yaml`、本地模型、运行日志、浏览器会话、OCR 截图和记忆数据库默认都属于本地运行期或敏感数据，不应提交。

当前真实浏览器、OCR、第三方 MCP、STT / TTS / API 的完整实机验收仍暂缓；离线自动化测试覆盖核心配置、UI 状态机和主要适配边界。
