# 开发流程

## 环境

- Python:
  `E:/Tool/Miniconda/envs/ai/python.exe`
- 安装依赖：
  `pip install -r requirements.txt`
- 运行：
  `python main.py`
- 测试：
  `python -m pytest tests/ -q`

## 阶段状态

- 第四阶段：已完成，主实现和文档已收口到当前架构文档。
- 第五阶段：已完成，进入稳定化维护。
- 第六阶段：实现、本地自动化验证和 sub agent 复审已完成；真实浏览器、OCR、MCP、STT / TTS / API 实机验收暂缓。
- 当前优先级：
  1. 暂缓中的实机验收恢复后，优先检查浏览器持续会话、OCR、MCP、STT / TTS / API 和平台日志联动
  2. 更多内置插件能力扩展

说明：

- 已完成并被主文档吸收的 spec / plan 应及时删除，避免入口持续指向历史收口材料
- 日志工作台基础能力已完成，后续只保留真实服务场景联调与增量体验优化
- Phase 4 中短期记忆由 `SessionContext` 负责，`mem0` 继续只做长期记忆
- 文档默认使用中文撰写；代码标识、路径、命令、配置键名和 git commit message 可保留英文
- 设计阶段中的关键数值（超时、并发数、窗口大小、预算上限等）默认应配置化，避免在 spec 中永久写死
- 当前仓库里已经存在不少历史硬编码参数；后续在对应模块重构、修复或增强时，应把这些参数逐步迁移为可配置项

## 文档层级

- 路线图：
  - 负责阶段目标、范围、依赖和验收边界
- 专题 spec：
  - 负责一个主题的设计决策、边界、风险和默认策略
- 实施计划：
  - 负责把已确认 spec 拆成可执行任务

当前文档统一采用上述层级，不建议混写。

## 配置文件

- `data/config/api.yaml`
  API 配置
  含 key，不应提交
  其中 TTS 的 `audio_mode`、`ref_audio_path`、`reference_mode`、`prompt_lang`、`output_lang`、`prompt_text` 控制运行态音频链路与参考策略
  其中 TTS 的 `ref_audio_path`、`reference_mode`、`prompt_lang`、`output_lang`、`prompt_text` 可能包含本地语音素材路径或私有参考文本，也按本地敏感配置处理
  其中 ASR / STT 配置位于 `asr`：当前字段为 `engine=faster_whisper`、`model_path`、`device`、`compute_type`、`transcribe_timeout_seconds`、`language`、`record_timeout_seconds`、`silence_threshold`、`silence_duration_ms`，通过本地 faster-whisper 库转写；默认 `device=cpu`、`compute_type=int8`，`device=auto` 也按 CPU 执行，避免无 CUDA 运行库环境误走 GPU
  Windows 下如使用 pip 安装 `nvidia-*-cu12` 运行库，STT 适配器会在进程内注册并持有对应 DLL 目录句柄，并把目录 prepend 到当前进程 `PATH`，以覆盖 CTranslate2 在真实解码阶段动态加载 `cublas64_12.dll` 的路径需求
- `data/config/system_config.yaml`
  系统配置
  当前也承载 `logging` 运行时配置，如日志根目录、平台日志内部 `system` channel 的 flush 间隔和 UI 内存事件窗口 `ui_buffer_limit`
  当前也承载 `chat_display` 与 `passive_interaction`：前者控制聊天字体倍率和气泡倍率；后者包含空闲阈值、被动气泡最大宽度和停留时长。被动状态属于聊天窗运行态，空闲阈值用于自动进入，不再使用系统级启用开关。
  当前也承载 `vision`：控制 OCR 是否启用、OCR 后端、OCR 语言、截图目录、最大文本长度和显式触发策略；默认后端为 `rapidocr`，`paddleocr` 为进阶可选后端。对应 UI 位于系统设置的 `视觉 / OCR` 分组，随系统配置保存；当前版本固定仅允许显式读屏触发。
  当前默认值：`chat_display.font_scale=1.3`，`passive_interaction.bubble_max_width=600`。
- `data/config/mcp.yaml`
  MCP 实际配置；每个 server 可配置 `connect_timeout_seconds`、`request_timeout_seconds` 和 `retry_attempts`
- `data/config/mcp.example.yaml`
  MCP 示例模板
- `data/config/memory.yaml`
  记忆配置
  含本地模型路径，不应提交
- `data/config/agent.yaml`
  Agent 默认配置
  当前已包含 `session_context`、`tts_runtime` 两组运行时配置
  可提交默认值，但个人临时调参不应随意提交
- `data/logs/`
  日志工作台默认输出目录
  `conversation/` 存放按 `session_id` 分文件的对话日志
  `system/` 存放按日期切分的平台日志；内部 channel 名仍为 `system`
  默认不应提交运行期产物
- `data/browser_sessions/`
  浏览器持续会话相关中间产物目录，默认不应提交
- `data/vision/`
  屏幕 OCR 截图中间产物目录，默认不应提交

## 配置化要求

- 关键体验参数不应长期散落在实现中硬编码
- 优先级更高的原则是：
  1. 先让参数进入配置层
  2. 再决定是否开放到设置界面
- Phase 4 当前已落地的配置入口：
  - `session_context.recent_turns_limit`
  - `session_context.working_facts_limit`
  - `session_context.prompt_facts_limit`
  - `session_context.prompt_turns_limit`
  - `session_context.constraint_ttl_turns`
  - `session_context.mem0_promotion_importance`
  - `tts_runtime.pcm_read_timeout_seconds`
  - `tts_runtime.segment_total_timeout_seconds`
  - `tts_runtime.max_translation_workers`
  - `tts_runtime.max_tts_workers`
  - `tts_runtime.tts_queue_limit`
  - `event_bus_runtime.log_max_buffer`
  - `event_bus_runtime.log_flush_interval_ms`
  - `event_bus_runtime.ui_dispatch_throttle_ms`
- Phase 5 当前已落地的配置入口：
  - `asr.engine`
  - `asr.model_path`
  - `asr.device`
  - `asr.compute_type`
  - `asr.transcribe_timeout_seconds`
  - `asr.language`
  - `asr.record_timeout_seconds`
  - `asr.silence_threshold`
  - `asr.silence_duration_ms`
  - `chat_display.font_scale`
  - `chat_display.bubble_scale`
  - `passive_interaction.idle_threshold_seconds`
  - `passive_interaction.bubble_max_width`
  - `passive_interaction.bubble_duration_seconds`
- Phase 5 已确认并已落地的改进配置入口：
  - 删除 `asr.base_url`、`asr.api_key`、`asr.api_url`、`asr.model`、`passive_interaction.enabled`
- Phase 6 当前已落地的配置入口：
  - `mcp.servers[].connect_timeout_seconds`
  - `mcp.servers[].request_timeout_seconds`
  - `mcp.servers[].retry_attempts`
  - `web_automation.browser_headless`
  - `web_automation.browser_timeout_ms`
  - `web_automation.page_wait_timeout_ms`
  - `web_automation.session_screenshot_dir`
  - `web_automation.max_extract_length`
  - `vision.enabled`
  - `vision.ocr_engine`
  - `vision.language`
  - `vision.screenshot_dir`
  - `vision.max_text_chars`
  - `vision.explicit_trigger_only`
- 以下类型默认都应朝配置化方向演进：
  - 短期记忆窗口、衰减、摘要预算
  - TTS 超时、并发、回退、队列长度
  - STT 录音与静音阈值
  - 被动互动频率、停留时长、显示策略
  - 浏览器自动化超时、OCR 显式触发策略、事件刷新频率

### 对 spec / plan 的要求

- spec 中如出现参数数值，必须明确其属于：
  - 示例值
  - 建议默认值
  - 或未来配置项候选
- plan 中如果展示示例代码，不应默认把关键参数直接写死为字面量，应尽量体现“由配置读取”的实现方向

## Git 约定

- 不提交真实 API key
- 不提交个人本地配置变更，除非明确需要
- 不提交 `data/models/`（本地模型目录）；新模型目录优先按 `data/models/embedding/` 与 `data/models/stt/` 分类放置，旧版 `data/models/<模型名>` 直属目录仅作为兼容路径保留；模型下拉框按规范化绝对路径去重，条目右侧 `×` 只移除列表项，不删除磁盘目录
- 不提交 `data/memory/`（运行时向量数据库）
- 提交信息沿用：
  - `feat: ...`
  - `fix: ...`
  - `docs: ...`

## 兼容性约束

- 原版兼容优先：涉及 GPT-SoVITS、MCP 或其他第三方系统时，必须先保证原版接口、默认行为和返回格式不变
- 魔改支持只能通过显式扩展实现：
  - 可选字段
  - 扩展端点语义
  - 向后兼容的新增响应字段或响应头
- 禁止为了兼容桌宠端或其他魔改客户端而：
  - 修改原版默认参数值
  - 改写原版必填项约束
  - 破坏原版成功 / 失败响应格式
- 文档、设计稿和实现计划都必须显式遵循以上原则，避免出现“以桌宠端为主导致原版失配”的表述
- 当前桌宠端的 TTS 模式边界：
  - `audio_mode=wav + reference_mode=inline` = 保底模式
  - `pcm_stream + inline` = 音频扩展，但不是当前服务端实现里的会话扩展
  - 只有带 `session_id` 的组合 = 会话扩展

## 测试策略

- 单元测试用 `pytest`
- 外部依赖优先 mock
- 浏览器相关行为优先区分：
  - 系统默认浏览器打开 / 搜索
  - Playwright 后台自动化 / 可见自动化
- 记忆相关改动优先覆盖非阻塞行为，避免对话结束后额外卡顿
- `session/` 相关改动优先覆盖：
  - `SessionContext` 数据演进
  - `SessionPolicy` 的约束提取与热上下文构建
  - `SessionPolicy` 的 `mem0` 升格候选筛选
  - SQLite 快照读写
  - `AgentManager -> LLMManager` 的短期上下文注入
- 日志工作台相关改动优先覆盖：
  - 结构化事件模型与脱敏
  - `LogService` 的筛选、导出与 JSONL 落盘
  - `SettingsWindow` 下的 `对话日志` / `平台日志` 页面入口；内部 channel 仍为 `conversation` / `system`
  - 关键运行链路的日志接线
  - `LogService` 内存事件窗口不得裁切待落盘 `_pending` 队列
  - `对话日志` / `平台日志` 页面不可见时应暂停自动刷新，重新显示时再刷新当前视图
  - 真实服务场景下的异常日志可见性与 UI 联动
- Phase 5 UI / STT 相关改动优先覆盖：
  - `SystemConfig.chat_display` 和 `SystemConfig.passive_interaction` 的默认值、持久化与设置页编辑
  - `APIConfig.asr` 的本地 faster-whisper 模型目录、设备、计算类型、识别超时、录音超时、静音阈值和静音时长
  - 被动状态自动进入、右键菜单切换、被动气泡显示、隐藏、尺寸上限、停留时长和主对话框互斥
  - 被动状态下拖拽 / 滚轮缩放不退出，点击气泡和右键菜单手动退出可恢复主对话框
  - 主动消息应基于角色上下文生成，支持 `[emotion:...]` 标签并驱动立绘切换；收到后必须复用普通聊天的切句、TTS 入队和平台日志链路
  - STT 按钮禁用、录音中、识别中、失败恢复和关闭窗口时 recorder / worker 生命周期治理
  - STT 录音、模型加载、转写、失败、超时和迟到结果忽略必须进入平台日志
  - `STTRecorder` 的无真实设备测试：PCM 静音检测、WAV 生成、超时与取消
  - `STTManager` 与 `FasterWhisperAdapter` 的本地 faster-whisper 库 mock 转写测试
  - STT 识别文本必须回到 `_on_send()`，不得绕过 Agent、SessionContext、日志或 TTS 管线
  - 真实麦克风、真实 faster-whisper 模型转写、真实 STT / TTS 互锁属于本地设备联调边界，不应作为离线 pytest 的硬依赖
- Phase 6 插件 / MCP / 浏览器 / OCR 相关改动优先覆盖：
  - `PluginHost` 的插件加载状态、失败消息和工具数量
  - `MCPHost` 的连接状态、工具名、错误类型、请求超时和重试
  - MCP 设置页新增 / 编辑弹窗对连接超时、请求超时、失败重试和启用状态保留的覆盖
  - `ToolRegistry` 的 `source_name` 与 qualified name 兼容
  - `web_automation` 既有搜索 / 提取 / 截图工具不回退，持续浏览器会话工具可打开、导航、等待、提取、点击、填写、查看状态和关闭
  - `VisionManager` 的禁用状态、截图失败、OCR 失败、文本截断和 RapidOCR / PaddleOCR 后端选择
  - `SessionContext.visual_observations` 的 prompt 注入和 SQLite 快照往返
  - `ChatWindow` 仅在显式读屏请求下主线程预采集截图；`AgentManager` 只处理预采集截图的 OCR 与会话注入，普通聊天不读屏
- TTS 性能相关改动优先覆盖：
  - GPT-SoVITS PCM 读取必须使用有界 chunk size，不得回退到 `chunk_size=None`
  - GPT-SoVITS WAV 回包必须按有界块发出，避免单个 Qt queued signal 携带整段音频
  - `ChatWindow` TTS 事件队列必须保持头部消费为 O(1)
  - PCM 播放缓冲读取后必须回收已读前缀，避免长语音内存持续增长
  - WAV 句段临时文件必须在播放完成、取消当前轮和关闭窗口时清理
- 启动窗口相关改动优先覆盖：
  - 无边框启动加载窗应支持左键拖拽移动
  - 内部 shell、标题、状态文字和进度条区域的鼠标事件也应能移动父窗口
- `EventBus` 相关改动优先覆盖：
  - 发布时 handler 快照语义
  - 订阅 / 退订与发布并发下的基本安全性
  - `UIEventBridge` 的主线程批量刷新与日志顺序
- UI 变更至少保证：
  - 行为测试
  - `py_compile`
  - 必要时 Qt offscreen 实例化
  - 聊天窗缩放 / 滚动类调整优先补回归测试
  - 聊天主链路状态反馈、停止 / 重试 / 打开日志入口和流式显示合帧应有聚焦测试
  - 立绘读图 / 缩放缓存应覆盖重复尺寸复用和缓存上限
  - 角色页面必须覆盖根目录核心文件删除保护，避免误删 `prompt.md`、`soul.md`、`SKILL.md` 或 `sprites.yaml`
  - 平台日志页面 UI 文案应统一使用“平台日志”，内部 channel 与落盘目录继续沿用 `system`
- TTS 相关改动优先覆盖：
  - `wav + inline` 下不得透传 `session_id`、不得调用 `set_refer_audio`、不得发送 PCM/流式扩展参数
  - `inline` 参考模式下，音频扩展与参考会话扩展必须解耦；允许 PCM 扩展但不得顺带透传 `session_id`
  - `audio_mode` 持久化与设置页 apply/reset
  - 原版 GPT-SoVITS 无 `session_id` 请求时的旧行为兼容
  - 新增扩展字段时不得改变原版 `wav` / 非流式默认路径
  - `SettingsWindow -> ChatWindow` 配置透传
  - `reference_mode` 持久化与 GPT-SoVITS 预热 / 回退策略
  - `GET /set_refer_audio?refer_audio_path=...` 调用方式与错误回退识别
  - `session_id` 预热扩展路径下 `prompt_lang` / `prompt_text` 的透传，以及缺失扩展参数时退回原版路径
  - `session_id` 对 `/set_refer_audio` 与 `/tts` 的透传
  - `auto` 模式的进程内能力探测缓存，避免同一服务端在单次运行里重复首句试错
  - `audio_mode=auto/pcm_stream/wav` 的请求参数映射与自动 WAV 回退
  - 句级切分边界（`。！？；` / 换行）
  - 长句软切分阈值与翻译模式更保守的分段策略
  - 情绪标签不得进入最终 TTS 文本
  - `prompt_lang` / `output_lang` 透传与语言别名兼容
  - 逐句翻译、旧轮失效、失败跳过与顺序播放
  - PCM 首个 chunk 到达即播、句段有序播放、失败后会话级 WAV 回退
  - PCM 流式请求必须使用有限读超时，不允许 `None` 式无限等待
  - 翻译 worker / 合成 worker 的并发上限与待处理队列推进
  - `TTSPipelineController` 的取消语义、队列上限与总超时
  - `wav` 句段应聚合完整字节后走共享播放器，不应为每句新建独立 `QMediaPlayer`
  - `ui/chat/audio_backends.py` 中 WAV / PCM 播放后端的无真实设备测试
  - 拟声词、语气词、拖长音、重复音节在翻译时优先保留音感，不被语义意译破坏
  - 避免依赖真实 GPT-SoVITS 服务或真实音频设备

### 当前聚焦回归入口

- Agent / EventBus：
  - `python -m pytest tests/test_config_agent.py -q`
  - `python -m pytest tests/test_event_bus.py tests/test_agent_page_events.py tests/test_agent_log_events.py -q`
- 日志工作台：
  - `python -m pytest tests/test_log_sanitizer.py tests/test_log_service.py tests/test_logging_integration.py -q`
  - `python -m pytest tests/test_conversation_log_page.py tests/test_system_log_page.py tests/test_settings_window.py -q`
  - 当前这些用例主要覆盖本地聚焦回归、日志内存窗口、页面可见性自动刷新和设置页入口；真实 API / TTS / 网络异常仍需手工联调验证
- TTS：
  - `python -m pytest tests/test_tts_pipeline.py tests/test_tts_adapter.py tests/test_chat_tts_flow.py -q`
- Phase 5 UI / STT：
  - `python -m pytest tests/test_chat_window_scale.py tests/test_chat_passive_bubble.py tests/test_chat_stt_flow.py tests/test_stt_adapter.py tests/test_stt_recorder.py tests/test_sprite_manager.py -q`
  - 当前这些用例主要覆盖无真实设备的配置、气泡、录音、本地 faster-whisper 库 mock、被动状态状态机、聊天窗状态条、流式显示合帧、立绘缓存、带字体预览的系统字体下拉框、系统页保存应用和聊天窗主链路；真实麦克风、真实 faster-whisper 模型转写和真实 STT / TTS 互锁仍需本地手工联调验证
- 语法检查：
  - 当前 UI / 日志关键实现：`python -m py_compile config/schema.py core/log_service.py ui/settings/window.py ui/settings/pages/api_page.py ui/settings/pages/system_page.py ui/settings/pages/conversation_log_page.py ui/settings/pages/system_log_page.py ui/chat/window.py ui/chat/sprite.py ui/chat/stt_recorder.py stt/types.py stt/adapter.py stt/adapters/faster_whisper.py stt/manager.py`

### TTS 归因边界

- 若桌宠端已正确传递 `session_id`、`prompt_lang`、`prompt_text`，则服务端 warmup 内部生成错误语言文本、或服务端内部切句产出 `、。` 等异常，应优先归因服务端。
- 桌宠端侧排查重点仍是：
  - 是否误把非目标语言文本直接送入 TTS
  - 是否在本地切句阶段提前产出异常分段
  - 是否在顺序播放状态机中额外引入等待

### TTS 模式总表

术语约定：

- `保底模式`：桌宠端强制只走原版显式参考字段工作流
- `音频扩展`：只扩展音频返回方式，例如 PCM 流式
- `会话扩展`：显式带 `session_id`，进入当前服务端实现的会话化参考路径

| 参考模式 | 客户端是否每次带显式参考 | 是否依赖 `set_refer_audio` | 是否依赖 `session_id` | 谁主导参考状态 | 兼容性定位 | 当前实测结果 |
|---|---|---|---|---|---|---|
| `inline` | 是 | 否 | 否；保底原版模式下明确禁用 | 客户端 | 原版基线 / 最保守 | 当前仅 `wav + inline` 可确认完全通过；若与 PCM 组合，仍有问题待处理 |
| `session_preload` | 通常首轮预热后尽量不带；失败时回退显式参考 | 是 | 是 | 客户端先灌入，服务端会话复用 | 会话扩展 | 已能跑通部分链路，但仍有扩展协商、warmup 或播放问题待处理 |
| `server_managed` | 通常不带 | 否或不依赖客户端主动预热 | 常见会依赖，但取决于服务端设计 | 服务端 | 会话扩展 / 最依赖服务端 | 目前未确认完全通过，仍需继续联调验证 |
| `auto` | 由客户端按探测结果决定 | 可能会 | 可能会 | 混合 | 客户端策略项 | 已具备回退链路，但整体仍未达到“完全无问题”；尤其 PCM 分支仍有待继续处理 |

| 音频模式 | 参考模式 | 当前定位 | 是否允许 `session_id` | 是否允许 `set_refer_audio` | 当前实测结果 | 说明 |
|---|---|---|---|---|---|---|
| `wav` | `inline` | 保底模式 | 否 | 否 | 完全通过，可作为当前唯一稳定保底组合 | 强制原版路径 |
| `wav` | `session_preload` | 会话扩展 | 是 | 是 | 部分通过，仍需继续联调验证 | 不流式，但走会话参考扩展 |
| `wav` | `server_managed` | 会话扩展 | 允许 | 通常不需要 | 目前未确认完全通过 | 参考完全交给服务端 |
| `wav` | `auto` | 客户端策略项 | 可能 | 可能 | 部分通过，但仍不作为当前稳定保底组合 | 客户端探测参考策略 |
| `pcm_stream` | `inline` | 音频扩展 | 否 | 否 | 存在问题，仍需继续处理 | 只扩展音频返回方式，不扩展参考会话 |
| `pcm_stream` | `session_preload` | 音频扩展 + 会话扩展 | 是 | 是 | 存在较多问题，需继续处理 | 当前最完整的低延迟会话方案 |
| `pcm_stream` | `server_managed` | 音频扩展 + 会话扩展 | 允许 | 通常不需要 | 目前未确认稳定 | 最依赖服务端实现 |
| `pcm_stream` | `auto` | 客户端策略项 | 可能 | 可能 | 问题最多，当前不应视为稳定方案 | 低延迟优先策略 |
| `auto` | 任意非 `wav + inline` 组合 | 客户端策略项 | 可能 | 可能 | 仍在演进中，不保证完全稳定 | 会先尝试扩展能力，再按策略回退 |

## 页面保存语义

### API 页面

- API 页面显示 `保存 API 配置`
- 点击后需确认
- 只保存 API 配置
- 切页即放弃未保存编辑

### 系统页面

- 系统页面显示 `保存系统配置`
- 点击后需确认
- 只保存系统配置
- 切页即放弃未保存编辑
- 保存成功后应用到已打开聊天窗，不保存 API 配置
- 保存失败时回滚内存配置、设置页草稿和已打开聊天窗配置，避免半保存状态

### 插件 / 角色页面

- 操作即时生效
- 成功 / 失败要有反馈

## 第三阶段进度

已完成：
1. 本地记忆系统（Mem0 OSS + Chroma + 本地向量模型）
2. 记忆设置页 UI
3. 记忆异步加载
4. Agent 模块（planner + executor + reflector + manager）
5. Agent 设置页日志混合时间线（用户输入 / 角色回复 / Thinking）
6. 聊天窗长文本滚动与整体缩放
7. 工具重复执行修复与聊天窗边框统一
8. 句级增量 TTS 播报接入（GPT-SoVITS）
9. 输出语言强约束与句级翻译播报
10. TTS 参考模式、会话预热与长句软切分优化
11. TTS `audio_mode`、PCM 流式播放与会话级 WAV 回退
