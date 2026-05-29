# Yumetsuki 文档入口

> 最后更新：2026-05-29

## 项目定位

Yumetsuki（梦月）是一个桌宠 AI 伴侣项目，核心体验是角色演出、自然对话、本地配置可控，以及可扩展的工具、语音、记忆、MCP、浏览器自动化和 OCR 能力。

当前主 UI 为 Tauri + Vue3 + Pinia + TypeScript 前端和 Python `python_core` headless sidecar。历史 PySide6 入口、旧 `ui/` 主实现和 PySide6 运行时依赖已从主线退场。

## 文档原则

- 原版兼容优先：涉及第三方服务、协议或接口时，先保证原版行为、默认参数和返回语义不变。
- 魔改兼容次之：对桌宠端或其他魔改客户端的支持必须通过显式扩展字段、可选能力或向后兼容的新增信息实现。
- 扩展能力必须显式触发：不能靠未知字段、原版字段或默认补全静默劫持原版请求。
- 禁止为了兼容魔改而修改原版默认值、原版必填项或原版返回格式。

## 当前进度

### Tauri UI 重构线

- 状态：Tauri/Vue 已是当前主 UI。
- 历史 UI：PySide6 入口、旧 Python 桌面 UI 主实现和 PySide6 依赖已退场。
- 当前边界：Vue typed client -> Tauri invoke/events -> Python stdio RPC。
- Python 内核：`python_core` 保留 Agent、LLM、TTS、STT、OCR、插件、MCP、配置、日志和记忆能力。
- 当前门槛：测试映射、RPC contract、no-PySide6 sidecar、发布安全 / 性能 gate 和文档 stale gate 必须持续通过。

### 后续风险

- 真实 API、TTS、STT、OCR、MCP 和 Playwright Edge 实机验收仍暂缓。
- Phase 7 smoke、Phase 8-A 真实 Mem0 联调和 1.0 验收门仍按 `docs/development.md` 记录收口。

## 入口文档

- [代码架构](./architecture.md)
  当前 Tauri / Vue / Python headless sidecar 架构、运行边界和核心流程。
- [开发流程](./development.md)
  环境、测试、发布 gate、配置和 1.0 验收门。
- [UI 规范](./ui-guidelines.md)
  当前 Vue / Sakura 组件和页面规范。
- [Tauri 桌面打包与发布安全](./release/desktop-packaging.md)
  lock 策略、发布扫描、Windows 干净机 smoke 和依赖升级流程。
- [插件与 MCP](./plugin-mcp.md)
  插件 SDK、宿主、MCP 配置与 transport。
- [系统控制插件](./plugin-system-control.md)
  打开应用、浏览器、文件、执行命令和权限等级。
- [Web 自动化插件](./plugin-web-automation.md)
  搜索、提取文本、截图和持续浏览器会话。
- [OCR 与视觉输入](./vision-ocr.md)
  屏幕 OCR、显式读屏触发、会话态注入和隐私边界。
- [服务端 TTS 对接规范](./service-tts-compatibility.md)
  服务端对接原则、允许与禁止变更边界、同步检查清单。
- [文档规范](./documentation-guidelines.md)
  文档语言、层级与参数配置化规则。

## 历史迁移归档

- [Tauri UI 重构发布级设计草案](./superpowers/specs/2026-05-28-tauri-ui-migration-design.md)
- [Tauri UI 迁移实施计划](./superpowers/plans/2026-05-29-tauri-ui-migration-implementation-plan.md)
- [后续阶段功能头脑风暴记录](./superpowers/brainstorms/2026-05-28-future-stage-brainstorm.md)
- [Phase 7 实机验收待补记录](./superpowers/smoke/2026-05-28-phase-7-smoke.md)
- [Phase 8 / Phase 9 阶段设计草案](./superpowers/specs/2026-05-28-phase-8-9-design.md)
- [Phase 8-A 记忆质量治理实施计划](./superpowers/plans/2026-05-28-phase-8-memory-ledger.md)
- [Phase 8-A 记忆账本实机验收待补记录](./superpowers/smoke/2026-05-28-phase-8-memory-ledger-smoke.md)

## 快速开始

Tauri 桌面工程：

- `pnpm install`
- `pnpm test`
- `pnpm dev`
- `pnpm e2e:smoke`
- `Set-Location apps/desktop/src-tauri; cargo test`
- `python -m pytest tests/rpc_contract/ -q`
- `python scripts/check_docs_no_stale_ui_status.py`
- `python scripts/check_no_pyside6_in_sidecar.py`
- `python scripts/check_release_manifest.py --bundle apps/desktop/src-tauri/target/release/bundle`

## 推荐阅读顺序

1. `docs/architecture.md`
2. `docs/development.md`
3. `docs/ui-guidelines.md`
4. `docs/plugin-mcp.md`
5. `docs/plugin-web-automation.md`
6. `docs/vision-ocr.md`
7. `docs/service-tts-compatibility.md`
