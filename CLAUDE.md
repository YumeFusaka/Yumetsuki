# CLAUDE.md — 协作上下文

## 作用

本文件只保留给 AI / 协作者的最小工作上下文。
详细内容不要继续堆在这里，统一查看 `docs/` 下的专题文档。

## 项目一句话

Yumetsuki 是一个 Python 桌宠 AI 伴侣项目，第四阶段已完成，第五阶段核心能力和改进实现已基本完成，当前进入用户实机测试、真实服务联调与 Phase 6 准备。

## 运行环境

- Python:
  `E:/Tool/Miniconda/envs/ai/python.exe`
- 运行：
  `python main.py`
- 测试：
  `python -m pytest tests/ -q`

## 关键约束

- 不提交真实 API key
- `data/config/api.yaml` 和 `data/config/memory.yaml` 默认视为本地敏感配置
- 优先沿用现有 UI 风格和提交信息格式
- 当前不引入 LangChain / LangGraph，继续走自定义架构
- 原版兼容优先：涉及第三方服务、协议或接口时，必须先保证原版行为与默认语义不被破坏；对魔改或桌宠端的支持只能通过显式扩展实现，不能靠改写原版默认值、原版必填项或原版返回格式达成
- 完成的功能同步更新文档：每次提交的改动必须同步更新 CLAUDE.md 和 docs/ 目录中的相关文档；已完成的 specs 和 plan 文件应及时删除或更新
- 所有文档必须使用中文
- 每个插件必须在 `docs/` 下有对应的说明文档（如 `docs/plugin-system-control.md`）

## 当前阶段

- 第一阶段：已完成（基础 UI、角色系统、LLM 对话）
- 第二阶段：已完成（插件系统、LLM 工具调用、MCP 接入、统一工具目录）
- 第三阶段：已完成
  - 本地记忆系统（Mem0 OSS + Chroma + 本地向量模型）
  - 记忆设置页 UI + 异步加载
  - Agent 分层智能架构（分层路由、异步反思、多步推理、主动行为）
  - Agent 设置页（多 Tab 配置）
  - Agent 日志混合时间线基础能力已完成，现已抽离到独立日志工作台继续演进
  - 系统控制插件（`plugins/system_control/`）：打开应用、系统默认浏览器、默认浏览器搜索、文件管理器、文件、URL、执行命令；三级权限控制
  - Web 自动化插件（`plugins/web_automation/`）：后台搜索、可见自动化搜索、提取文本、截图；Playwright + Edge；三级权限控制
  - 桌宠聊天窗优化：面板体感更宽、面板高度收紧、立绘落点下移、长文本内部滚动、整体缩放驱动字体/按钮/边框同步变化、文本压缩多余段间空白
  - 聊天窗边框修正：默认对话框 3px、输入框和圆形按钮 2px 纯玫瑰色边框；整体缩放时边框厚度同步按比例变化，并设最小值；hover/focus 使用更深玫瑰色
  - Agent 工具调用修正：tool 模式下禁止后续 LLM 二次调用同轮工具
  - 句级增量 TTS 播报与服务端兼容能力已接入：支持句级合成、输出语言约束、参考模式 / 预热与兼容回退，以及 `audio_mode=auto/pcm_stream/wav`
  - ChatWindow 在窗口生命周期内生成 TTS `session_id`，仅用于显式扩展路径下的 GPT-SoVITS speaker 会话化
  - `auto` 模式优先请求 PCM 流式，若流式失败则在当前聊天会话内锁定为 WAV；原版默认 `/tts` 语义与无扩展字段请求保持不变
  - `audio_mode=wav + reference_mode=inline` 被定义为桌宠端保底模式：不调用 `set_refer_audio`、不透传 `session_id`、不发送 PCM/流式扩展参数
  - `pcm_stream + inline` 属于音频扩展，但不属于会话扩展；只有带 `session_id` 的组合才进入当前服务端实现的会话扩展路径
  - 当前已完成的多数 TTS 扩展能力属于桌宠端通用能力（模式边界、流式事件模型、播放后端、顺序播放状态机）；GPT-SoVITS 只是首个服务端适配器实现
  - 当前已确认的剩余 TTS 异常（如服务端 warmup 文本语言选择错误、`、。` 之类切分异常）归因服务端；在桌宠端已正确传递 `session_id`、`prompt_lang`、`prompt_text` 的前提下，不再视为本仓库当前已知根因
- 第四阶段：已完成
  - 已完成：
    - `SessionContext` 配置、数据模型、`SessionPolicy`、`SessionContextStore`、`SessionContextManager`
    - `AgentManager -> LLMManager` 短期上下文热路径接线
    - `SessionPolicy` 的 `recent_turns` / `working_facts` 配置化裁切
    - `mem0` 保守升格边界与去重升格标记
    - `SessionContextStore` 的 `working_facts` SQLite 快照
    - `EventBus` 基础线程安全与发布快照语义
    - `UIEventBridge` 主线程桥与 Agent 日志批量刷新接线
    - GPT-SoVITS PCM 有限读超时
    - 聊天窗 TTS 翻译 / 合成 worker 上限与待处理队列
    - `TTSPipelineController` 句段生命周期、取消语义、队列上限与总超时轮询
    - `wav + inline` 句段改走共享 WAV 播放器路径，避免每句创建独立 `QMediaPlayer`
    - 流式前缀漂移时禁止已提交 TTS 前缀重复入队，收口重复播报问题
  - 已完成验收：
    - Phase 4 聚焦回归通过
    - `python -m pytest tests/ -q` 全量测试通过
    - 关键模块 `py_compile` 语法检查通过
  - 后续配套能力已落地：
    - 日志工作台基础版：`LogService`、脱敏、JSONL 持久化、`对话日志` / `平台日志` 独立页面
    - `ChatWindow`、`AgentManager`、`LLMManager`、`ToolRegistry`、`GPTSoVITSAdapter` 已接入结构化运行日志
    - 日志工作台打磨已完成：平台日志支持业务链路 / 来源两层筛选、结构化列表 / 连续文本双视图、自由选择复制、自动刷新滚动保持、详情区稳定刷新；对话日志改为最近会话选择与当前 / 全部会话切换
    - 平台日志 UI 细节已收口：已知来源使用唯一配色，结构化列表选中态通过绘制委托保持来源文字色，连续文本视图沿用来源配色，刷新重建时不会把列表、连续文本或详情区强制弹到底部；设置中心右键菜单、标准文本复制 / 粘贴菜单与下拉框箭头已统一为浅色 Sakura 主题
    - 设置中心导航已收口：页面顺序固定为 `API / 角色 / 记忆 / Agent / 插件 / 对话日志 / 平台日志 / 系统`；`API` 使用钥匙图标，`Agent` 保留机器人图标；导航点击目标与高亮状态按页面索引绑定
    - 日志覆盖已补强：记忆检索、短期上下文构建、LLM 流式进度、LLM 本地切句、TTS 入队与翻译完成均有平台日志记录；内部日志 channel 仍为 `system`，`llm.stream_progress` 已做长度阈值节流，避免长回复日志风暴
    - 当前状态为“基础能力完成，已通过聚焦自动化回归，但尚未完成真实服务场景的全面联调验证”
- 第五阶段：基本完成，等待用户实机测试与真实联调
  - 显示配置已接入：`SystemConfig.chat_display` 支持聊天字体倍率与气泡倍率，设置中心系统页可编辑，`ChatWindow` 启动时应用到字体、按钮、输入框、边框和气泡尺寸。
  - 被动状态已改为聊天窗运行态：空闲达到 `passive_interaction.idle_threshold_seconds` 后自动进入，右键菜单可手动进入 / 退出；只有被动状态下的主动消息使用独立气泡。
  - STT 配置已收敛为 faster-whisper 本地服务：`APIConfig.asr` 支持 `engine`、`api_url`、`model`、`language`、录音超时、静音阈值和静音时长。
  - STT 模块已落地：`stt/` 提供 `STTResult`、`STTAdapter`、`FasterWhisperAdapter`、`STTManager`，当前唯一有效适配器通过 `{api_url}/transcribe` 调用本地 faster-whisper 服务。
  - 录音链路已落地：`ui/chat/stt_recorder.py` 使用 Qt 麦克风输入采集 PCM，支持静音检测、超时停止和 WAV 字节生成。
  - 主链路接入已落地：聊天窗麦克风按钮可启动录音、进入转写 worker，识别文本回到 `_on_send()`，复用 Agent、SessionContext、日志与 TTS 管线；关闭窗口时会治理 recorder 与 worker 生命周期。
  - 系统页已改为基础外观、聊天显示、被动状态、被动气泡、网络五组；字体控件使用带字体预览的系统字体下拉框；系统页独立显示 `保存系统配置`，只保存系统配置，并在保存后应用到已打开聊天窗。
  - 当前边界：相关自动化测试曾覆盖配置、设置页、被动状态、录音状态、适配器和聊天窗主链路；本轮按用户要求不再执行自动化测试，真实 faster-whisper 服务、真实麦克风和真实 STT / TTS 互锁由后续实机联调验证。

## 下一步

- 继续推进 Phase 5 / Phase 6：
  - 真实麦克风、真实 faster-whisper 服务、真实 STT / TTS / API 场景联调
  - 更多内置插件能力扩展（媒体控制、文件操作等）
  - 平台日志补做真实 API / TTS / 异常场景的全面联调验证

## 文档入口

- [文档入口](./docs/README.md)
- [代码架构](./docs/architecture.md)
- [UI 规范](./docs/ui-guidelines.md)
- [插件与 MCP](./docs/plugin-mcp.md)
- [开发流程](./docs/development.md)
- [服务端 TTS 对接规范](./docs/service-tts-compatibility.md)
- [Phase 4-6 路线图设计](./docs/superpowers/specs/2026-05-24-phase-4-6-roadmap-design.md)
- [Phase 5 改进设计](./docs/superpowers/specs/2026-05-25-phase-5-stt-passive-settings-refinement-design.md)
- [Phase 5 改进实施计划](./docs/superpowers/plans/2026-05-25-phase-5-stt-passive-settings-refinement-implementation.md)
