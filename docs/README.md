# Yumetsuki 文档入口

> 最后更新：2026-05-26

## 项目定位

Yumetsuki（梦月）是一个 Python 桌宠 AI 伴侣项目，第三阶段与第四阶段已完成，第五阶段核心链路和 faster-whisper / 被动状态 / 系统设置保存语义改进已基本完成，当前进入用户实机测试与真实服务联调阶段。

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
- [Phase 6：浏览器、视觉与插件生态设计](./superpowers/specs/2026-05-24-phase-6-browser-vision-ecosystem-design.md)
  第六阶段的浏览器、视觉与插件 / MCP 增强设计
- [Phase 6 插件 / MCP 诊断实施计划](./superpowers/plans/2026-05-26-phase-6-plugin-mcp-diagnostics-implementation.md)
  插件加载状态、MCP 连接诊断、工具来源与重试超时配置的任务拆解
- [Phase 6 浏览器持续会话实施计划](./superpowers/plans/2026-05-26-phase-6-browser-session-implementation.md)
  Playwright 持续浏览器会话、页面动作工具与配置化超时的任务拆解
- [Phase 6 OCR 与视觉输入实施计划](./superpowers/plans/2026-05-26-phase-6-ocr-vision-implementation.md)
  屏幕 OCR、视觉观察会话态和显式读屏触发的任务拆解
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
  - 日志工作台基础版：独立 `对话日志` / `平台日志` 页面、结构化事件、JSONL 持久化、详情复制与导出
  - 日志工作台打磨：平台日志支持业务链路 / 来源两层筛选、结构化列表 / 连续文本双视图、自由选择复制、自动刷新滚动保持、详情区稳定刷新
  - 平台日志 UI 细节收口：已知来源使用唯一配色，选中结构化列表项时通过绘制委托保留来源文字色，连续文本视图沿用来源配色；自动刷新不会在用户翻阅历史或详情时强制弹到底部
  - 设置中心 UI 细节收口：导航顺序固定为 API / 角色 / 记忆 / Agent / 插件 / 对话日志 / 平台日志 / 系统；右键菜单、标准文本复制 / 粘贴菜单和全部设置页下拉框统一为浅色 Sakura 主题；下拉框统一复用 `ui.theme.SAKURA_COMBO_BOX_STYLE` 与 `ui/assets/combo-down.svg`
  - 对话日志打磨：最近会话下拉、当前会话 / 全部会话切换、情绪标签胶囊样式优化
  - 日志覆盖补强：记忆检索、短期上下文构建、LLM 流式进度、LLM 本地切句、TTS 入队与翻译完成、STT 录音 / 模型加载 / 转写 / 超时均已接入平台日志；`llm.stream_progress` 已节流
  - 日志工作台当前状态：已具备主题化 UI、完整运行时间线、错误接线、双层筛选、连续文本复制、来源配色、滚动保持与关键链路日志覆盖；尚未完成真实服务场景的全面联调验证
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
- 第五阶段：已完成，进入稳定化维护
  - 显示配置：`SystemConfig.chat_display` 已支持聊天字体倍率和气泡倍率，系统设置页可编辑，聊天窗启动时应用到字体、按钮、输入框、边框与气泡尺寸。
  - 被动状态：已从系统设置开关改为聊天窗运行态，支持空闲阈值自动进入和右键菜单手动切换；被动状态下主动消息使用独立气泡。
  - 被动显示：进入被动状态后主对话框立即隐藏，气泡自动隐藏后仍保持被动隐藏；拖拽和滚轮缩放不退出被动状态，点击气泡或右键菜单手动退出后恢复主对话框。
  - 主动行为：闲置主动发言 prompt 必须基于角色上下文和情绪标签规则生成，并按闲置时长引入温柔、不安、撒娇、赌气、委屈、生气等变化；主动消息会驱动立绘情绪切换，并复用普通聊天的切句、TTS 入队与平台日志链路。
  - 显示默认值：聊天字号倍率默认 `1.3`，被动气泡最大宽度默认 `600px`，气泡和 toast 宽度按文本单行宽度测算，超过最大宽度或窗口可用宽度才换行。
  - STT 配置：`APIConfig.asr` 已收敛为本地 faster-whisper 库参数：引擎、模型目录、设备、计算类型、识别超时、语言、录音超时、静音阈值和静音时长；默认使用 `cpu/int8`，模型目录优先使用 `data/models/stt/`，并兼容旧版 `data/models/` 直属目录。
  - STT 适配层：`stt/` 已提供 `STTResult`、`STTAdapter`、`FasterWhisperAdapter` 和 `STTManager`，当前唯一有效适配器直接加载本地 faster-whisper 模型目录并转写 WAV；`device=auto` 按 CPU 执行，显式 `cuda` 会注册并注入 pip NVIDIA CUDA 12 DLL 路径以支持 CTranslate2 真实解码。
  - STT 录音层：`ui/chat/stt_recorder.py` 已提供 Qt 麦克风录音、PCM 静音检测、超时停止和 WAV 字节生成。
  - STT 主链路：聊天窗麦克风按钮已接入录音、转写 worker 和 `_on_send()`，识别文本复用现有 Agent、SessionContext、日志与 TTS 管线；识别超时会释放当前 UI 状态并记录平台日志，关闭窗口时治理 recorder 与 worker 生命周期。
  - 线程治理：聊天窗关闭时会统一请求 LLM / STT / TTS / 翻译 / 参考预热线程停止并等待收口，避免 `QThread` 仍运行时被释放。
  - 系统设置：字体已改为带字体预览的系统字体下拉框；系统页拆分为基础外观、聊天显示、被动状态、被动气泡和网络；系统页独立保存并在保存后应用到已打开聊天窗。
  - 当前边界：离线自动化测试曾覆盖配置、气泡、录音、适配器和聊天窗 STT 主链路；真实麦克风、真实 faster-whisper 模型转写和真实 STT / TTS / API 互锁体验由后续实机联调验证。
- 第六阶段：已完成实施计划拆解，等待进入编码实施
  - 插件 / MCP 管理增强
  - 浏览器高级操控
  - OCR 与视觉能力

## 下一步方向

- Phase 6 按路线图继续推进浏览器、视觉与插件生态能力
- 继续补强真实 API / TTS / 异常场景下的平台日志联调验证

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
3. `docs/superpowers/specs/2026-05-24-phase-6-browser-vision-ecosystem-design.md`
4. `docs/superpowers/plans/2026-05-26-phase-6-plugin-mcp-diagnostics-implementation.md`
5. `docs/superpowers/plans/2026-05-26-phase-6-browser-session-implementation.md`
6. `docs/superpowers/plans/2026-05-26-phase-6-ocr-vision-implementation.md`
7. `docs/plugin-mcp.md`
8. `docs/service-tts-compatibility.md`
9. `docs/development.md`
10. `docs/ui-guidelines.md`
