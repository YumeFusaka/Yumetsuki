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
├── llm/
├── tts/
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
  设置中心主窗口
- `ui/settings/pages/api_page.py`
  API 配置页面
- `ui/settings/pages/system_page.py`
  系统设置页面
- `ui/settings/pages/character_page.py`
  角色管理页面
- `ui/settings/pages/plugin_page.py`
  插件与 MCP 管理页面
- `ui/chat/window.py`
  桌宠聊天窗（长文本滚动、整体缩放、对话面板布局、句级增量 TTS、TTS `session_id` 生命周期、句段流式状态机）
- `ui/chat/audio_backends.py`
  TTS 播放后端：`WavPlaybackBackend` 负责完整 WAV 播放，`PcmStreamPlaybackBackend` 负责 PCM 边收边播
- `ui/chat/sprite.py`
  立绘加载、缩放、情绪切换

### `config/`

负责配置模型和持久化。

- `config/schema.py`
  Pydantic 配置模型
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
  对话历史、流式输出、工具调用循环
- `llm/text_processor.py`
  解析 `[emotion:xxx]`

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
  `audio_mode=wav + reference_mode=inline` 被实现为桌宠端保底模式：不调用 `set_refer_audio`、不透传 `session_id`、不发送 PCM/流式扩展参数，只保留原版显式参考字段工作流
  `pcm_stream + inline` 被实现为音频扩展：只扩展音频返回方式，不进入当前服务端以 `session_id` 判定的会话扩展路径

### `core/`

负责非 UI 的基础能力。

- `core/event_bus.py`
  发布 / 订阅事件总线
- `core/character.py`
  角色目录加载
- `core/plugin_host.py`
  本地插件发现与调用
- `core/mcp_host.py`
  MCP server 会话、tools/list、tools/call
- `core/tool_registry.py`
  统一聚合本地插件工具和 MCP 工具

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
  网页自动化插件：后台搜索、可见自动化搜索、提取文本、截图（Playwright + Edge）
  内部分模块：browser.py（浏览器管理）、search.py（搜索引擎）、page.py（页面操作）
  三级权限控制（low/medium/high）

### `data/`

项目数据目录。

- `data/config/`
  配置文件
- `data/characters/`
  角色包

## 对话主流程

```text
用户输入
→ AgentManager 编排当前轮
→ LLMManager 组装 messages
→ ToolRegistry 注入 tool schemas
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
→ ChatWindow 按句段顺序驱动 `WavPlaybackBackend` 或 `PcmStreamPlaybackBackend`
→ Qt 多媒体按句序播放音频；PCM 在首个可播 chunk 到达后尽快起播
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

设置中心「Agent」页面（多 Tab）订阅这些事件，日志页会把用户输入、角色回复、Thinking 预览和内部事件合并为一条时间线显示。

### 配置

`data/config/agent.yaml`，对应 `config/schema.py` 中的 `AgentConfig`：

- `PlannerConfig` — 升级阈值、关键词列表
- `ReflectorConfig` — 深层反思开关、触发条件
- `MultiStepConfig` — 最大步数、超时时间
- `ProactiveConfig` — 启用开关、闲置间隔、冷却时间、活跃时段、自定义事件列表

## 当前能力边界

第三阶段已完成，项目具备：

- 插件 SDK + 插件宿主
- OpenAI-compatible tool calling
- MCP stdio / HTTP(SSE) transport
- 统一工具目录（ToolRegistry）
- 本地记忆系统（Mem0 OSS + Chroma + 本地向量模型）
- 异步记忆加载
- Agent 分层智能（路由、反思、多步推理、主动行为）
- Agent 日志混合时间线
- 聊天窗长文本滚动与整体缩放
- 句级增量 TTS 播报（GPT-SoVITS，支持参考预热与软切分）
- PCM 流式低延迟播放（`audio_mode=pcm_stream`）
- `auto` 模式下的会话级 WAV 回退
- 输出语言强约束与句级翻译播报（拟声词 / 语气词优先保留音感）

尚未实现：

- 更多内置插件能力扩展（媒体控制、截图等）

## 已确认的后续演进方向

当前已确认的路线图见：

- [Phase 4-6 路线图设计](./superpowers/specs/2026-05-24-phase-4-6-roadmap-design.md)

其中对当前架构影响最大的下一阶段是 Phase 4，核心收敛方向如下：

- 新增 `SessionContext` 短期记忆层，位于 UI / Agent / 长期记忆之间
- 把多轮连续性建立在“单会话工作记忆”之上，而不是仅依赖原始 `_history` 或长期记忆检索
- 把聊天主路径拆为首字热路径与深能力层，避免所有能力默认争抢首字前关键路径
- 治理 EventBus 线程边界与 TTS 分段流水线，降低长时间运行时的卡死和状态错乱风险

### `session/`（Phase 4 目标模块）

以下模块属于已确认的 Phase 4 设计目标，当前仓库尚未落地：

- `session/context.py`
  `SessionContext`、`SessionTurn`、`WorkingFact`、`ActiveTask`、`SessionSummary`
- `session/policy.py`
  当前会话工作记忆更新规则、热上下文构建、长期记忆升格边界
- `session/store.py`
  SQLite 快照持久化
- `session/manager.py`
  面向 `AgentManager` 的高层短期记忆门面

目标状态下，对话主路径会补充以下约定：

- 首字热路径优先依赖 `SessionContext` 的短期上下文块，而不是先依赖深记忆检索
- 长期记忆补充位于短期会话上下文之后

后续架构文档应在 Phase 4 落地后同步更新：

- `SessionContext` 模块与存储边界
- Agent / Planner / Memory 的新时序
- TTS 固定流水线与取消语义
- UI 被动互动、STT、视觉与浏览器自由操控在后续阶段中的接入点

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
用户输入 → AgentManager 检索相关记忆 → 注入 extra_context → LLM 生成回复
回复完成 → UI 立即解锁输入
       → 后台线程写入 Mem0/Chroma
       → 后台线程执行反思与深层记忆提取
```
