# CLAUDE.md — 协作上下文

## 作用

本文件只保留给 AI / 协作者的最小工作上下文。详细内容统一查看 `docs/` 下的专题文档。

## 项目一句话

Yumetsuki 是一个桌宠 AI 伴侣项目，当前主 UI 已切到 Tauri shell + Vue3 组合式 + Pinia + TypeScript，并通过 Python `python_core` headless sidecar 承载业务内核。

历史 PySide6 入口、旧 `ui/` 主实现和 PySide6 运行时依赖已退场。当前状态不是旧版产品完整复刻完成态，功能和 UI parity 恢复以 `docs/tauri-parity-recovery.md` 为准。

## 运行环境

- Python: `E:/Tool/Miniconda/envs/ai/python.exe`
- Tauri / Vue：
  - `pnpm install`
  - `pnpm dev`
  - `pnpm dev:web`
  - `pnpm test; pnpm e2e:smoke`
  - `Set-Location apps/desktop/src-tauri; cargo test`
  - `python -m pytest tests/rpc_contract/ -q`

## 关键约束

- 不提交真实 API key。
- `data/config/api.yaml`、`data/config/memory.yaml` 和本地模型默认视为本地敏感配置。
- 优先沿用现有 UI 风格和提交信息格式。
- 当前不引入 LangChain / LangGraph，继续走自定义架构。
- 原版兼容优先：涉及第三方服务、协议或接口时，必须先保证原版行为与默认语义不被破坏；对魔改或桌宠端的支持只能通过显式扩展实现，不能靠改写原版默认值、原版必填项或原版返回格式达成。
- 完成的功能同步更新文档：每次提交的改动必须同步更新 `docs/` 目录中的相关文档。
- 所有文档必须使用中文。

## 当前阶段

### Tauri UI 重构线

- 状态：Tauri/Vue 已作为当前主 UI；历史 PySide6 入口已删除；产品级功能和 UI parity 未完成。
- 设计入口：`docs/superpowers/specs/2026-05-28-tauri-ui-migration-design.md`
- 实施计划：`docs/superpowers/plans/2026-05-29-tauri-ui-migration-implementation-plan.md`
- 目标通信链路：Vue typed client -> Tauri invoke/events -> Python stdio RPC。
- 退场状态：PySide6、旧 `ui/` 主实现和旧文档入口已移除。
- 当前门槛：测试映射、RPC contract、no-PySide6 sidecar、发布安全 / 性能 gate 和文档 stale gate 必须保持通过；旧版功能和 UI 恢复必须按 `docs/tauri-parity-recovery.md` 建立矩阵并逐项验收。

- 第一阶段：已完成（基础 UI、角色系统、LLM 对话）
- 第二阶段：已完成（插件系统、LLM 工具调用、MCP 接入、统一工具目录）
- 第三阶段：已完成
  - 本地记忆系统（Mem0 OSS + Chroma + 本地向量模型）
  - 记忆设置页 UI + 异步加载
  - Agent 分层智能架构（分层路由、异步反思、多步推理、主动行为）
  - Agent 设置页（多 Tab 配置）
  - 日志工作台基础能力已完成，现已抽离到独立日志工作台继续演进
  - 系统控制插件（`plugins/system_control/`）：打开应用、系统默认浏览器、默认浏览器搜索、文件管理器、文件、URL、执行命令；三级权限控制
  - Web 自动化插件（`plugins/web_automation/`）：后台搜索、可见自动化搜索、提取文本、截图、持续浏览器会话；Playwright + Edge；三级权限控制
  - 桌宠聊天窗优化：面板体感更宽、面板高度收紧、立绘落点下移、长文本内部滚动、整体缩放驱动字体/按钮/边框同步变化、文本压缩多余段间空白
  - 句级增量 TTS 播报与服务端兼容能力已接入：支持句级合成、输出语言约束、参考模式 / 预热与兼容回退，以及 `audio_mode=auto/pcm_stream/wav`
  - 当前已完成的多数 TTS 扩展能力属于桌宠端通用能力；GPT-SoVITS 只是首个服务端适配器实现
- 第四阶段：已完成
  - `SessionContext`、`SessionContextStore`、`SessionContextManager`
  - `AgentManager -> LLMManager` 短期上下文热路径接线
  - `EventBus` 基础线程安全与发布快照语义
  - `UIEventBridge` 主线程桥接和 Agent 日志批量刷新接线
  - `TTSPipelineController` 句段生命周期、取消语义、队列上限与总超时轮询
  - 流式前缀漂移时禁止已提交 TTS 前缀重复入队
- 第五阶段：已完成，进入稳定化维护
  - 显示配置、被动状态、被动气泡和 STT 链路已收口。
  - 系统页、聊天窗和设置中心已经改为当前 Tauri / Vue 主线。
- 第六阶段：实现完成，本地自动化验证和复审通过，实机验收暂缓
  - 插件 / MCP / 浏览器 / OCR 已接入。
  - 产品级收口已补充：运行状态条、停止当前生成、失败重试、日志入口、流式显示合帧、立绘缓存和 TTS 音频回传性能补强。

## 下一步

- 先按 `docs/tauri-parity-recovery.md` 获取旧版截图、建立功能矩阵，并恢复旧版功能和 UI 样式。
- 继续维护 Tauri 迁移后的测试映射、RPC contract、发布安全和性能预算 gate。
- 真实 API / TTS / STT / OCR / MCP / Playwright Edge 实机验收按 `docs/development.md` 的 1.0 验收门推进。
- `docs/superpowers/` 下的迁移计划和 smoke 记录仅作为历史归档。

## 文档入口

- [文档入口](./docs/README.md)
- [代码架构](./docs/architecture.md)
- [UI 规范](./docs/ui-guidelines.md)
- [Tauri 产品 Parity 恢复计划](./docs/tauri-parity-recovery.md)
- [开发流程](./docs/development.md)
- [Tauri 桌面打包与发布安全](./docs/release/desktop-packaging.md)
- [插件与 MCP](./docs/plugin-mcp.md)
- [OCR 与视觉输入](./docs/vision-ocr.md)
- [服务端 TTS 对接规范](./docs/service-tts-compatibility.md)
