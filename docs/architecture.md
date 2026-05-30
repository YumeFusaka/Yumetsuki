# Yumetsuki 代码架构

## 总览

Yumetsuki 当前采用轻量本地架构，核心目标是：

- 角色演出优先
- 工具调用可扩展
- 本地配置与数据可控
- 不依赖 LangChain / LangGraph 等外部 Agent 框架

## 目录结构

```text
yumetsuki/
├── main.py
├── core/
├── config/
├── session/
├── llm/
├── tts/
├── stt/
├── vision/
├── ui/
├── data/
├── plugins/
└── tests/
```

## 核心模块

### `main.py`

- 应用入口
- 初始化 Qt 应用和全局样式
- 打开设置中心

### `ui/`

负责桌面 UI。

- `ui/settings/window.py`
  设置中心主窗口；导航顺序固定为 `API / 角色 / 记忆 / Agent / 插件 / MCP / 对话日志 / 平台日志 / 系统`
- `ui/theme.py`
  Sakura 主题共享模块，集中提供右键菜单浅色主题、浅色 tooltip、设置中心下拉框样式与公共 UI 资源路径，并通过应用 palette 兜底避免系统黑底 tooltip 泄漏
- `ui/settings/pages/api_page.py`
  API 配置页面
- `ui/settings/pages/system_page.py`
  系统设置页面；当前已将外观相关配置拆分为基础外观、聊天显示、被动状态、被动气泡、视觉 / OCR 和网络区域，字体下拉框按字体自身样式预览；视觉 / OCR 分组包含被动状态定时读屏、读屏间隔、截图保留时长、截图数量上限和清理间隔
- `ui/settings/pages/character_page.py`
  角色页面；角色根目录核心文件 `prompt.md`、`soul.md`、`SKILL.md`、`sprites.yaml` 在 UI 中禁止删除，避免误破坏角色包
- `ui/settings/pages/plugin_page.py`
  插件管理页面；管理本地插件、内置插件权限和外部插件导入，展示插件加载状态、工具数量、说明和诊断详情
- `ui/settings/pages/mcp_page.py`
  MCP 管理页面；管理 MCP server、连接诊断和 MCP 工具列表，新增 / 编辑弹窗覆盖 transport、命令或 URL、连接超时、请求超时和失败重试，展示连接状态、工具数量、错误类型和诊断详情
- `ui/settings/pages/conversation_log_page.py`
  对话日志页面，展示会话级结构化事件；正文优先展示，工具调用和关联记忆作为底部 meta strip，自动刷新不会打断用户拖选文本
- `ui/settings/pages/system_log_page.py`
  平台日志页面，展示 TTS / LLM / STT / Tool 等运行期平台事件；结构化列表和连续文本视图共享上方 stack，下方 JSON 详情区通过 splitter 可拉伸；长条目自动换行且不要求横向滚动，内部日志 channel 与落盘目录仍沿用 `system`
- `ui/chat/window.py`
  桌宠聊天窗（长文本滚动、显示配置、被动互动气泡、STT 语音输入、整体缩放、对话面板布局、聊天运行状态条、停止 / 重试 / 打开日志入口、流式回复显示合帧、句级增量 TTS、TTS `session_id` 生命周期、句段流式状态机、总超时轮询；WAV 句段聚合后走共享播放器，PCM 句段走流式 backend；同时产出 TTS 句段与播放相关系统日志）
  被动互动已从系统设置开关改为聊天窗运行态：空闲阈值自动进入、右键菜单手动切换、被动状态下主动消息走气泡
- `ui/chat/stt_recorder.py`
  Qt 麦克风录音控制器，负责 PCM 采集、静音检测、超时停止和 WAV 字节生成；录音完成后交由聊天窗的 STT worker 转写
- `ui/chat/audio_backends.py`
  TTS 播放后端：`PcmStreamPlaybackBackend` 负责 PCM 边收边播；完整 WAV 在当前聊天窗主路径下由共享 `QMediaPlayer` 顺序播放
- `ui/chat/tts_pipeline.py`
  `TTSPipelineController` 负责句段状态、取消语义、队列上限与总超时判定
- `ui/chat/sprite.py`
  立绘加载、缩放、情绪切换；对原图和近期目标尺寸缩放结果做小型缓存，降低滚轮缩放和情绪切换时的重复读图 / 平滑缩放成本

### `config/`

负责配置模型和持久化。

- `config/schema.py`
  Pydantic 配置模型
  当前已包含 `SessionContextConfig`、`TTSRuntimeConfig`、`EventBusRuntimeConfig`、`ChatDisplayConfig`、`PassiveInteractionConfig`、`VisionConfig`，其中 `ASRConfig` 已收敛为本地 faster-whisper 模型目录、转写超时、录音超时、静音阈值、静音结束时长和起始静音等待，`PassiveInteractionConfig` 已收敛为被动运行态阈值和气泡显示参数，`VisionConfig` 除显式读屏外还可选配置被动状态定时读屏间隔、截图保留时长、截图数量上限和清理间隔
- `config/manager.py`
  YAML 读写，当前支持：
  - `api.yaml`
  - `system_config.yaml`
  - `mcp.yaml`
  - `memory.yaml`
  - `agent.yaml`

### `llm/`

负责对话和工具调用。

- `llm/adapter.py`
  LLM 适配器抽象
- `llm/adapters/openai_compat.py`
  OpenAI-compatible 接口实现
- `llm/manager.py`
  对话历史、短期上下文注入、流式输出、工具调用循环
- `llm/text_processor.py`
  解析 `[emotion:xxx]`

### `session/`

负责单会话短期记忆与热路径上下文。

- `session/context.py`
  `SessionContext`、`SessionTurn`、`WorkingFact`、`ActiveTask`、`SessionSummary`、最近视觉观察
- `session/policy.py`
  当前会话工作记忆更新规则、约束提取、热上下文构建，以及保守的 `mem0` 升格候选筛选
- `session/store.py`
  SQLite 快照持久化
- `session/manager.py`
  面向 `AgentManager` 的高层短期记忆门面

### `tts/`

负责语音能力适配。

当前结构分为两层：

- 桌宠端通用 TTS 能力层
  负责模式边界、流式事件抽象、PCM/WAV 播放后端、句段顺序播放与回退策略
- 服务端协议适配层
  负责把上述通用能力映射到具体 TTS 框架；当前已落地的是 `GPTSoVITSAdapter`

- `tts/adapter.py`
  TTS 适配器抽象，统一暴露 `stream_synthesize()` 流式事件接口，并保留 `synthesize()` 兼容包装
- `tts/types.py`
  TTS 流式事件与音频格式模型（`TTSStreamEvent`、`TTSAudioFormat`）
- `tts/adapters/gptsovits.py`
  GPT-SoVITS HTTP 适配器
  提供 HTTP 合成请求、流式事件输出与基础失败日志
  会把基础地址规范化到 `/tts`，支持 `reference_mode` 参考策略：逐次携带、会话预热、自动回退或完全由服务端托管；可在启动聊天后异步通过 `GET /set_refer_audio?refer_audio_path=...` 预热参考，并在需要时只向 `/tts` 发送正文与输出语言；若 `auto` 模式探测到目标服务端仍要求逐次携带参考，会在当前进程内缓存该能力判断，避免重复首句试错
  同时支持 `audio_mode=auto/pcm_stream/wav`：在显式扩展路径下可透传 `session_id`、`prompt_lang`、`prompt_text`、请求 PCM chunk stream，并在当前聊天会话内按需锁定 WAV 回退
  PCM 流式请求现已使用有限读超时，避免 `None` 式无限等待
  `audio_mode=wav + reference_mode=inline` 被实现为桌宠端保底模式：不调用 `set_refer_audio`、不透传 `session_id`、不发送 PCM/流式扩展参数，只保留原版显式参考字段工作流
  `pcm_stream + inline` 被实现为音频扩展：只扩展音频返回方式，不进入当前服务端以 `session_id` 判定的会话扩展路径

### `stt/`

负责语音转文本能力适配。

- `stt/types.py`
  STT 转写结果模型，统一承载文本、语言和错误信息
- `stt/adapter.py`
  STT 适配器抽象，当前统一暴露 `transcribe_wav()`，输入为 WAV 字节
- `stt/adapters/faster_whisper.py`
  本地 faster-whisper 库适配器，懒加载 `ASRConfig.model_path` 指向的模型目录，并直接转写录音生成的 WAV 字节；默认使用 `cpu/int8`，`device=auto` 在桌宠端按 CPU 执行，只有显式 `cuda` 才走 GPU；模型加载、转写开始、完成、失败和空结果会写入平台日志
- `stt/manager.py`
  根据 `ASRConfig.engine` 创建适配器；`none` 表示禁用语音输入，`faster_whisper` 创建 `FasterWhisperAdapter`，未知引擎返回可展示错误

### `vision/`

负责屏幕 OCR 与视觉文本输入。

- `vision/types.py`
  `ScreenRegion`、`OCRResult`、`VisualObservation`
- `vision/screen_capture.py`
  使用 Qt 主屏截图并保存到 `SystemConfig.vision.screenshot_dir`；默认截图名包含微秒、纳秒片段和进程内计数器，避免高频读屏同秒覆盖；只清理该目录下非递归的 `screen_*.png`
- `vision/ocr.py`
  `RapidOCRAdapter` 作为默认本地 OCR 后端，`PaddleOCRAdapter` 作为进阶可选后端
- `vision/manager.py`
  `VisionManager.capture_screen_image()` 负责主线程截图封装，`recognize_image_text()` 负责 OCR 与截断；`capture_screen_text()` 仅保留为兼容旧调用的组合方法
  被动状态定时读屏会先在主线程截图，再由后台 worker 做 OCR，结果回写 `SessionContext.visual_observations` 并作为主动发言参考；启动、截图前和聊天窗定时器都会按配置清理过期或超量截图

### `core/`

负责非 UI 的基础能力。

- `core/event_bus.py`
  发布 / 订阅事件总线
  当前已具备加锁订阅、退订与发布时 handler 快照语义
- `core/ui_event_bridge.py`
  Qt 主线程桥；把后台线程发布的 UI 相关事件与日志批量回送到主线程消费
- `core/log_types.py`
  结构化日志事件模型与 channel / level 常量
- `core/log_sanitizer.py`
  日志脱敏规则：屏蔽 `api_key`、`authorization`、`cookie` 等敏感字段
- `core/log_service.py`
  统一日志入口、内存查询、JSONL 落盘、筛选导出
- `core/character.py`
  角色目录加载
- `core/plugin_host.py`
  本地插件发现与调用，并输出插件加载诊断状态
- `core/mcp_host.py`
  MCP server 会话、tools/list、tools/call、连接状态、工具名、错误类型与重试
- `core/tool_registry.py`
  统一聚合本地插件工具和 MCP 工具，并记录工具来源名称

### `sdk/`

负责插件开发接口。

- `sdk/base.py`
  `BasePlugin`
  `@tool`
  工具 schema 生成

### `plugins/`

本地插件目录。

- 每个插件一个目录
- 至少包含 `plugin.py`
- 示例插件：`plugins/example_echo/`
- `plugins/system_control/`
  系统控制插件：打开应用、系统默认浏览器、默认浏览器搜索、文件管理器、文件、URL、执行命令
  内部分模块：open.py（打开类）、command.py（命令执行）
  三级权限控制（low/medium/high）
- `plugins/web_automation/`
  网页自动化插件：后台搜索、可见自动化搜索、提取文本、截图、持续浏览器会话（Playwright + Edge）
  内部分模块：browser.py（浏览器管理与持续会话）、session.py（会话结果模型）、search.py（搜索引擎）、page.py（页面操作）
  三级权限控制（low/medium/high）

### `data/`

项目数据目录。

- `data/config/`
  配置文件
- `data/characters/`
  角色包

## 对话主流程

```text
语音输入
→ STTRecorder 采集麦克风 PCM、检测静音并生成 WAV
→ STTManager 调用当前 STT 适配器转写
→ ChatWindow 将识别文本写入输入框并调用 _on_send()
用户文本输入
→ ChatWindow 判断是否为显式读屏、当前页面阅读或浏览器上下文读屏请求
→ 如需读屏，则 ChatWindow 在 Qt 主线程通过 VisionManager.capture_screen_image() 预采集截图
→ AgentManager 编排当前轮
→ SessionContextManager 同步更新当前会话短期记忆
→ 若本轮有预采集截图，则 AgentManager 在后台 OCR 并写入 SessionContext.visual_observations
→ LLMManager 按“角色提示 → SessionContext 热上下文 → 长期记忆补充 → 当前输入”组装 messages
→ ToolRegistry 按当前轮权限注入 tool schemas；当前页面阅读、默认浏览器直接上下文和已有默认浏览器上下文下的点击 / 阅读请求会禁用 LLM 工具调用
→ OpenAI-compatible API 流式返回
→ TextProcessor 解析 emotion
→ 如有 tool call，则通过 ToolRegistry 分发执行
→ tool result 回填给模型
→ UI 显示文本并切换立绘
→ TextProcessor 与 ChatWindow 会剥离 `[emotion:...]` 等情绪标签，避免它们进入 TTS
→ ChatWindow 按 `。！？；` / 换行切句，并在长句达到阈值时优先按 `，、：` / 空格软切分
→ 若句子与目标输出语言不一致，则逐句调用 LLM 翻译
→ 翻译前会对拟声词、语气词、拖长音、重复音节做音感保护标注，提示模型优先保留发音感觉与节奏
→ 翻译结果进入 GPT-SoVITS 合成
→ GPT-SoVITS 依据 `audio_mode` 返回完整 WAV 或 PCM chunk stream
→ ChatWindow 按句段顺序驱动 WAV 临时文件播放或 `PcmStreamPlaybackBackend`
→ 翻译 worker / TTS worker 受 `AgentConfig.tts_runtime` 限流，超额句段先进入待处理队列
→ Qt 多媒体按句序播放音频；PCM 在首个可播 chunk 到达后尽快起播，WAV 句段落到临时文件后以本地文件 URL 播放
```

TTS 音频事件必须避免在 Qt 主线程做长时间同步工作：

- 句段事件队列使用 `deque`，避免大量 chunk 到达时 `pop(0)` 造成 O(n) 消费成本。
- GPT-SoVITS PCM 回包使用固定 chunk size 读取，WAV 回包按有界块发出，避免单个 queued signal 携带超大 bytes。
- PCM 播放缓冲会回收已读前缀，避免长语音让内存缓冲持续增长。
- WAV 句段不再在主线程聚合为整段 bytes 后塞入 `QBuffer`，而是写入进程临时文件，播放完成、取消当前轮或关闭窗口时统一清理。

Phase 5 改进后的 STT 适配路径将固定为：

```text
STTRecorder
→ STTManager
→ FasterWhisperAdapter
→ 本地 faster-whisper 库与模型目录
→ STTResult
→ ChatWindow._on_stt_result()
→ ChatWindow._on_send()
```

已知边界：

- 当桌宠端已经正确传递 `session_id`、`prompt_lang`、`prompt_text` 后，服务端 warmup 内部语言选择错误、服务端内部切句导致的 `、。` 之类异常，不归因于本仓库当前桌宠端实现

## 工具系统

当前工具来源有两类：

- 本地插件工具
- MCP 工具

两者统一进入 `ToolRegistry`，由它负责：

- 汇总工具 schema
- 统一刷新
- 调用分发
- 提供 UI 展示数据

## Agent 系统

Agent 层采用分层智能架构，核心设计原则：**简单对话零开销，复杂任务按需升级**。

### 模块结构

- `agent/planner.py` — 分层路由（快速关键词匹配 → LLM 判断）
- `agent/executor.py` — 工具调用执行
- `agent/reflector.py` — 异步反思（浅层摘要 / 深层 LLM 记忆提取）
- `agent/multi_step.py` — 多步推理（Plan→Execute→Observe 循环）
- `agent/proactive.py` — 主动行为调度器（定时 + 事件驱动）
- `agent/llm_helper.py` — Agent 内部 LLM 调用（非流式）
- `agent/manager.py` — Agent 编排器
  当前已接入 `SessionContextManager`，在首字热路径中同步记录用户输入、构建短期上下文，并在回复完成后回写 assistant turn

### 分层路由（Planner）

```text
用户输入
→ 快速关键词匹配（零 API 调用）
  → 命中：直接返回路由结果
  → 未命中 + 触发升级条件：调用 LLM judge
    → LLM 返回路由决策（chat / tool / multi_step）
```

升级条件：输入含工具关键词、问号、多句等复杂信号。

浏览器相关路由约定：

- “打开浏览器”优先走系统控制插件的默认浏览器工具
- “用浏览器搜索 xxx”优先走系统控制插件的默认浏览器搜索工具
- “搜索 xxx”“帮我搜一下 xxx”会在无更具体工具命中时归一化为真实关键词后走默认浏览器搜索；Planner 决策会写入 `agent.planner_decided`
- “看看你搜索的这个页面有什么内容”“总结当前网页”这类当前页面阅读请求是硬边界：Planner 不升级到 LLM judge，AgentManager 在执行工具前也会二次强制回 chat + OCR
- “点击浏览器里的条目”这类针对用户已打开系统默认浏览器的指令不得自动打开 `web_session_open`；除非用户明确要求 Playwright / 自动化浏览器 / 持续会话
- 执行过默认浏览器打开或默认浏览器搜索后，AgentManager 会记录当前处于默认浏览器上下文；后续“打开第二个条目”“点第二个”“看看这个结果”等省略“浏览器”的短句会优先触发 OCR 并禁用 LLM 工具调用，避免误开第二个浏览器或把阅读意图当作搜索词
- “后台搜索并返回结果”“提取网页内容”“截图网页”优先走 `web_automation`
- `web_search_visible` 仅用于明确要求展示 Playwright 自动化搜索过程的场景

### 异步反思（Reflector）

- 浅层反思：每轮对话后提取关键点（纯文本处理，无 API 调用）
- 深层反思：满足条件时（长回复、情感内容）后台线程调用 LLM 提取记忆写入 Mem0

### 多步推理（MultiStepRunner）

- 由 Planner 判断触发（`needs_multi_step=True`）
- Plan→Execute→Observe 循环，带 max_steps 和 timeout 保护
- 通过 EventBus 发布进度事件

### 主动行为（ProactiveScheduler）

- QThread 后台运行，5 秒 tick
- 闲置定时器：用户长时间不交互时主动发言
- 自定义事件：可注册触发器（如工作提醒）
- 全局冷却 + 事件独立冷却 + 活跃时段过滤
- 所有参数可在设置中心配置
- 主动发言会注入当前角色上下文和情绪标签规则；闲置越久越倾向不安、撒娇、赌气、委屈或生气等更强情绪，但仍必须贴合角色
- 聊天窗收到主动消息后复用 `TextProcessor` 剥离 `[emotion:...]`，驱动立绘情绪切换，并作为新一轮角色回复进入普通切句、TTS 入队和平台日志链路；被动状态只改变显示为气泡，不绕过 TTS

### Agent 事件日志

Agent 通过 `EventBus` 发布内部行为事件：

- `agent.user_input` — 用户输入
- `agent.assistant_reply` — 角色回复完成
- `agent.thinking` — Thinking 预览
- `agent.planner_decided` — Planner 路由决策
- `agent.memory_retrieved` — 记忆检索结果
- `agent.tool_executed` — 工具执行
- `agent.tool_skipped` — 跳过工具调用
- `agent.llm_started` — LLM 开始生成
- `agent.llm_complete` — LLM 生成完成
- `agent.reflection_complete` — 反思完成
- `agent.multi_step_progress` — 多步推理进度

这些事件仍由 Agent 发布到 `EventBus`；但设置中心里的运行日志职责已经从 `Agent` 页面抽离，改为独立日志工作台承接结构化回看能力。

## 日志工作台

日志工作台当前分为两层：

- `conversation`
  用户输入、角色回复等对话级事件
- `system`
  TTS、LLM、Tool、运行期错误与回退事件

当前主链路中，`ChatWindow`、`AgentManager`、`LLMManager`、`ToolRegistry` 与 `GPTSoVITSAdapter` 都可向 `LogService` 写入结构化 `LogEvent`。`LogService` 会先做脱敏，按 `LoggingConfig.ui_buffer_limit` 保留内存事件窗口，再按 channel 写入 `data/logs/` 下的 JSONL 文件：

- `data/logs/conversation/<session_id>.jsonl`
- `data/logs/system/YYYY-MM-DD.jsonl`

当前页面形态：

- `对话日志`
  面向聊天回看，突出用户 / 角色主线，并补充时间、情绪、工具、记忆摘要；页面不可见时暂停自动刷新，避免后台重建日志视图抢占 UI 主线程
- `平台日志`
  面向排障与运行回看，展示完整程序运行时间线；默认上半区为高密度日志流，下半区按选中事件显示详情；结构化列表展示时间、级别、来源、事件类型、短 session id 和关键参数摘要，完整 JSON 保留在详情区；页面不可见时暂停自动刷新，选中详情、拖选文本和滚动位置在刷新时保持稳定
  页面名为“平台日志”，内部日志 channel 与落盘目录仍沿用 `system`

当前边界：

- 基础能力与聚焦回归已完成
- 真实 API 超时、真实 TTS 失败、长时间运行等场景仍需继续联调验证

### 配置

`data/config/agent.yaml`，对应 `config/schema.py` 中的 `AgentConfig`：

- `PlannerConfig` — 升级阈值、关键词列表
- `ReflectorConfig` — 深层反思开关、触发条件
- `MultiStepConfig` — 最大步数、超时时间
- `ProactiveConfig` — 启用开关、闲置间隔、冷却时间、活跃时段、自定义事件列表
- `SessionContextConfig` — recent turns、working facts、热上下文相关上限
- `TTSRuntimeConfig` — PCM 读超时、单句超时候选、翻译 / 合成并发上限、队列上限
- `EventBusRuntimeConfig` — 日志缓冲上限、批量刷新间隔、UI 分发节流参数

## 当前能力边界

第三阶段已完成，项目具备：

- 插件 SDK + 插件宿主
- OpenAI-compatible tool calling
- MCP stdio / HTTP(SSE) transport
- 统一工具目录（ToolRegistry）
- 本地记忆系统（Mem0 OSS + Chroma + 本地向量模型）
- 异步记忆加载
- Agent 分层智能（路由、反思、多步推理、主动行为）
- 日志工作台首版（对话 / 平台双页面，内部 `conversation` / `system` 双通道、结构化持久化与导出）
- 聊天窗长文本滚动与整体缩放
- 句级增量 TTS 播报（GPT-SoVITS，支持参考预热与软切分）
- PCM 流式低延迟播放（`audio_mode=pcm_stream`）
- `auto` 模式下的会话级 WAV 回退
- 输出语言强约束与句级翻译播报（拟声词 / 语气词优先保留音感）
- 运行期结构化日志接线与 JSONL 持久化
- TTS 句段生命周期治理（取消、队列上限、总超时）
- Phase 5 显示配置基础能力：聊天字体倍率、气泡倍率、设置中心系统页编辑与聊天窗启动应用
- Phase 5 被动互动气泡：主动消息可独立气泡展示，支持默认 `600px` 最大宽度、停留时长、主对话框互斥、顶部与主对话框上边缘对齐，以及随整体缩放响应
- Phase 5 STT 链路：API ASR 配置、Qt 麦克风录音、PCM 静音检测、WAV 生成、本地 faster-whisper 模型转写和 `_on_send()` 主链路接入；默认 CPU/int8 降低 CUDA 环境依赖，识别超时会释放当前 UI 状态并记录平台日志，迟到结果会被忽略
- Phase 5 改进实现：STT 已改为本地 faster-whisper 库与模型目录；被动互动已改为聊天窗运行态；系统页已改为系统字体下拉框、独立保存和保存后应用

当前边界：

- 更多内置插件能力扩展（媒体控制、截图等）
- 第六阶段实现、本地自动化验证和 sub agent 复审已完成；真实浏览器、OCR、MCP、STT / TTS / API 实机验收暂缓

## 已完成的阶段性架构收敛

已经完成并对当前架构影响最大的近阶段收敛如下：

- 新增 `SessionContext` 短期记忆层，位于 UI / Agent / 长期记忆之间
- 把多轮连续性建立在“单会话工作记忆”之上，而不是仅依赖原始 `_history` 或长期记忆检索
- 把聊天主路径拆为首字热路径与深能力层，避免所有能力默认争抢首字前关键路径
- 治理 EventBus 线程边界与 TTS 分段流水线，降低长时间运行时的卡死和状态错乱风险

### `session/`（Phase 4 已落地的首批模块）

当前仓库已落地以下首批短期记忆模块：

- `session/context.py`
- `session/policy.py`
- `session/store.py`
- `session/manager.py`

当前对话主路径已具备以下约定：

- 首字热路径优先依赖 `SessionContext` 的短期上下文块，而不是先依赖深记忆检索
- 长期记忆补充位于短期会话上下文之后

后续演进重点：

- 日志工作台与结构化可观测性
- 实机验收恢复后，优先检查真实浏览器持续会话、真实 OCR、MCP 服务端、STT / TTS / API 和平台日志联动

## 记忆系统

### `memory/`

负责对话记忆存储与检索。

- `memory/mem0_store.py`
  Mem0MemoryStore 封装 + build_local_mem0_store 本地构造器
  依赖 Mem0 OSS + Chroma 向量数据库
  向量模型使用 huggingface 本地 SentenceTransformer

### 记忆配置

- `data/config/memory.yaml`
  配置字段：
  - `enabled`：是否启用本地记忆
  - `storage_dir`：本地持久化根目录（chroma + history.db）
  - `embedding_model_path`：本地向量模型路径（可以是 data/models/ 下的模型，也可以是外部路径）
  - `top_k`：每次检索返回的最大记忆条数

### 记忆流程

```text
启动聊天 → 聊天窗口立即显示（无等待）
       → 后台线程加载向量模型
       → 模型就绪后注入 AgentManager
用户输入 → AgentManager 先更新 `SessionContext` 并构建热上下文
       → 检索相关长期记忆 → 注入 extra_context → LLM 生成回复
回复完成 → UI 立即解锁输入
       → 后台线程把反思结果与保守筛选后的短期稳定事实写入 Mem0/Chroma
       → 后台线程执行反思与深层记忆提取
```
