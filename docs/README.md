# Yumetsuki 文档入口

> 最后更新：2026-05-24

## 项目定位

Yumetsuki（梦月）是一个 Python 桌宠 AI 伴侣项目，第三阶段已完成，第四阶段现已完成。

## 文档原则

- 原版兼容优先：涉及第三方服务、协议或接口时，先保证原版行为、默认参数和返回语义不变
- 魔改兼容次之：对桌宠端或其他魔改客户端的支持必须通过显式扩展字段、可选能力或向后兼容的新增信息实现
- 扩展能力必须显式触发：不能靠未知字段、原版字段或默认补全静默劫持原版请求
- 禁止为了兼容魔改而修改原版默认值、原版必填项或原版返回格式

## 文档结构

### 入口文档

- `docs/README.md`
  作为文档导航入口

### 协作文档

- `CLAUDE.md`
  面向 AI / 协作者的最小工作上下文

### 专题文档

- [代码架构](./architecture.md)
  模块结构、主流程、工具系统、Agent 系统、记忆系统
- [UI 规范](./ui-guidelines.md)
  主题、控件、反馈、交互约定
- [插件与 MCP](./plugin-mcp.md)
  插件 SDK、宿主、MCP 配置与 transport
- [开发流程](./development.md)
  环境、配置、测试、保存语义、Git 约定
- [服务端 TTS 对接规范](./service-tts-compatibility.md)
  服务端对接原则、允许与禁止变更边界、同步检查清单
- [Phase 4-6 路线图设计](./superpowers/specs/2026-05-24-phase-4-6-roadmap-design.md)
  第四到第六阶段的目标、范围、依赖与验收边界
- [日志工作台设计](./superpowers/specs/2026-05-24-logging-workbench-design.md)
  对话日志 / 系统日志分层、结构化事件与持久化设计
- [日志工作台实施计划](./superpowers/plans/2026-05-24-logging-workbench-implementation.md)
  日志工作台的可执行实施计划（基础能力已落地）
- [日志工作台打磨设计](./superpowers/specs/2026-05-24-logging-workbench-polish-design.md)
  日志覆盖面、滚动行为、复制体验与筛选模型的二次打磨设计
- [Phase 5：桌宠体验、UI 与 STT 设计](./superpowers/specs/2026-05-24-phase-5-ui-stt-design.md)
  第五阶段的桌宠体验、界面与语音输入设计
- [Phase 6：浏览器、视觉与插件生态设计](./superpowers/specs/2026-05-24-phase-6-browser-vision-ecosystem-design.md)
  第六阶段的浏览器、视觉与插件 / MCP 增强设计
- [文档规范](./documentation-guidelines.md)
  文档语言、层级与参数配置化规则

### 插件文档

- [系统控制插件](./plugin-system-control.md)
  打开应用、浏览器、文件、执行命令；三级权限
- [Web 自动化插件](./plugin-web-automation.md)
  搜索、提取文本、截图；Playwright + Edge；三级权限

## 当前进度

- 第一阶段：已完成（基础 UI、角色系统、LLM 对话）
- 第二阶段：已完成（插件系统、LLM 工具调用、MCP 接入、统一工具目录）
- 第三阶段：已完成
  - 本地记忆系统（Mem0 OSS + Chroma + 本地向量模型）
  - 记忆设置页 UI + 异步加载
  - Agent 分层智能架构（路由、反思、多步推理、主动行为）
  - Agent 设置页（多 Tab：规划/反思/多步推理/主动行为）
  - 日志工作台基础版：独立 `对话日志` / `系统日志` 页面、结构化事件、JSONL 持久化、详情复制与导出
  - 日志工作台当前状态：已具备主题化 UI、完整运行时间线、错误接线与基础筛选；尚未完成真实服务场景的全面联调验证
  - 系统控制插件（打开应用、浏览器、文件、执行命令；三级权限）
  - Web 自动化插件（搜索、提取文本、截图；Playwright + Edge；三级权限）
  - 桌宠聊天窗视觉与排版优化（更宽面板、更轻毛玻璃、更紧凑多段文本、长文本内部滚动、整体等比缩放）
  - 聊天窗边框统一为纯玫瑰色实边，并按窗口缩放动态调整厚度
  - 副作用工具重复执行修复
  - 句级增量 TTS 播报接入（GPT-SoVITS，硬断句 + 长句软切分、后台合成、顺序播放、失败跳过）
  - TTS 输出语言强约束（参考语言/输出语言分离，逐句翻译后播报，保证播报语言与设置一致；拟声词 / 语气词优先保留音感）
  - TTS 参考模式与启动预热（支持自动回退、会话初始化一次、服务端托管参考，以及进程内能力探测缓存）
  - TTS 音频模式 `auto / pcm_stream / wav`，支持 ChatWindow 级 `session_id`、PCM 边收边播与会话级 WAV 回退
  - TTS 模式边界已收紧：`wav + inline` 为保底模式；`pcm_stream + inline` 为音频扩展；只有带 `session_id` 的组合才属于当前服务端实现的会话扩展
  - 当前已完成的多数 TTS 扩展能力属于桌宠端通用能力，可复用于后续其他 TTS 框架；GPT-SoVITS 只是首个适配器实现
  - 当前已确认的剩余 TTS 异常归因服务端：桌宠端在显式扩展路径下已正确透传 `session_id`、`prompt_lang`、`prompt_text`；若仍出现 warmup 语言选择错误或 `、。` 之类切分异常，应优先在服务端排查
- 第四阶段：已完成
  - 已完成前半段：
    - `SessionContext` 短期记忆系统
    - `SessionContextStore` SQLite 快照
    - `AgentManager -> LLMManager` 首字热路径接线
    - `mem0` 保守升格边界
    - `EventBus` 基础线程安全
    - GPT-SoVITS 有限 PCM 读超时
    - TTS worker 上限与待处理队列
  - 已完成后半段核心收口：
    - `UIEventBridge` 主线程桥与 Agent 日志批量刷新接线
    - Agent 日志页退订治理与桥接消费
    - `TTSPipelineController` 句段生命周期、取消语义、队列上限与总超时轮询
    - PCM 流式错误事件语义回归
    - `wav + inline` 改走共享 WAV 播放器路径
    - 流式前缀漂移时禁止已提交 TTS 前缀重复入队
  - 已完成验收：
    - Phase 4 聚焦回归通过
    - `python -m pytest tests/ -q` 全量测试通过
    - 关键模块 `py_compile` 语法检查通过
- 第五阶段：已确认范围，暂未展开实施计划
  - 桌宠体验与交互输入输出
  - 系统设置 / 聊天界面优化
  - STT 接入
- 第六阶段：已确认范围，暂未展开实施计划
  - 插件 / MCP 管理增强
  - 浏览器高级操控
  - OCR 与视觉能力

## 下一步方向

- Phase 5、Phase 6 按路线图顺序推进
- 继续补强日志工作台的联调验证、筛选体验与更多运行链路覆盖

## 快速开始

- 安装依赖：
  `pip install -r requirements.txt`
- 启动：
  `python main.py`
- 测试：
  `python -m pytest tests/ -q`

## 推荐阅读顺序

1. `docs/architecture.md`
2. `docs/superpowers/specs/2026-05-24-phase-4-6-roadmap-design.md`
3. `docs/superpowers/specs/2026-05-24-logging-workbench-design.md`
4. `docs/superpowers/plans/2026-05-24-logging-workbench-implementation.md`
5. `docs/plugin-mcp.md`
6. `docs/service-tts-compatibility.md`
7. `docs/development.md`
8. `docs/ui-guidelines.md`
