# CLAUDE.md — 协作上下文

## 作用

本文件只保留给 AI / 协作者的最小工作上下文。
详细内容不要继续堆在这里，统一查看 `docs/` 下的专题文档。

## 项目一句话

Yumetsuki 是一个 Python 桌宠 AI 伴侣项目，第四阶段已完成，第五阶段核心能力和改进实现已完成，第六阶段实现、本地自动化验证和 sub agent 复审已完成；当前已补充一轮产品级体验、性能和文档一致性收口，真实浏览器、OCR、MCP 与语音服务实机验收暂缓。

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
  - Web 自动化插件（`plugins/web_automation/`）：后台搜索、可见自动化搜索、提取文本、截图、持续浏览器会话；Playwright + Edge；三级权限控制
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
    - 日志工作台打磨已完成：平台日志支持业务链路 / 来源两层筛选、结构化列表 / 连续文本双视图、自由选择复制、自动刷新滚动保持、详情区稳定刷新；对话日志改为最近会话选择与当前 / 全部会话切换；对话日志与平台日志页面不可见时暂停自动刷新
    - `LogService` 使用 `LoggingConfig.ui_buffer_limit` 控制内存事件窗口，避免长时间运行时 UI 日志缓存无限增长，同时不裁切待落盘队列
    - 平台日志 UI 细节已收口：已知来源使用唯一配色，结构化列表选中态通过绘制委托保持来源文字色，连续文本视图沿用来源配色，刷新重建时不会把列表、连续文本或详情区强制弹到底部；设置中心右键菜单、标准文本复制 / 粘贴菜单与下拉框箭头已统一为浅色 Sakura 主题
    - 设置中心导航已收口：页面顺序固定为 `API / 角色 / 记忆 / Agent / 插件 / MCP / 对话日志 / 平台日志 / 系统`；`API` 使用钥匙图标，`Agent` 保留机器人图标；导航点击目标与高亮状态按页面索引绑定
    - 日志覆盖已补强：记忆检索、短期上下文构建、LLM 流式进度、LLM 本地切句、TTS 入队与翻译完成、STT 录音 / 模型加载 / 转写 / 超时均有平台日志记录；内部日志 channel 仍为 `system`，`llm.stream_progress` 已做长度阈值节流，避免长回复日志风暴
    - 当前状态为“基础能力完成，已通过聚焦自动化回归，但尚未完成真实服务场景的全面联调验证”
- 第五阶段：已完成，进入稳定化维护
  - 显示配置已接入：`SystemConfig.chat_display` 支持聊天字体倍率与气泡倍率，设置中心系统页可编辑，`ChatWindow` 启动时应用到字体、按钮、输入框、边框和气泡尺寸。
  - 被动状态已改为聊天窗运行态：空闲达到 `passive_interaction.idle_threshold_seconds` 后自动进入，右键菜单可手动进入 / 退出；只有被动状态下的主动消息使用独立气泡。
  - 被动状态显示已收口：进入被动状态后立即隐藏主对话框，气泡自动隐藏后仍保持被动隐藏；拖拽和滚轮缩放只刷新空闲计时，不退出被动状态；点击被动气泡或右键菜单手动选择退出后恢复主对话框。
  - 主动行为发言已增强：闲置 prompt 必须基于当前角色上下文和情绪标签规则生成，并按闲置时长引入温柔、不安、撒娇、赌气、委屈、生气等情绪变化；主动消息会解析 `[emotion:...]`、切换立绘，并复用普通聊天的切句、TTS 入队与平台日志链路。
  - 被动气泡显示默认值已调大：`chat_display.font_scale` 默认 `1.3`，`passive_interaction.bubble_max_width` 默认 `600`，气泡宽度按文本单行宽度测算，超过最大宽度或窗口可用宽度才换行，并随聊天窗整体缩放响应。
  - STT 配置已收敛为本地 faster-whisper 库：`APIConfig.asr` 支持 `engine`、`model_path`、`device`、`compute_type`、`transcribe_timeout_seconds`、`language`、录音超时、静音阈值和静音时长；默认使用 `cpu/int8`，模型路径优先 `data/models/stt/...`，同时兼容旧版 `data/models/...`。
  - STT 模块已落地：`stt/` 提供 `STTResult`、`STTAdapter`、`FasterWhisperAdapter`、`STTManager`，当前唯一有效适配器直接加载本地 faster-whisper 模型目录并转写 WAV；`device=auto` 在桌宠端按 CPU 执行，显式 `cuda` 会注册并注入 pip NVIDIA CUDA 12 DLL 路径以支持 CTranslate2 真实解码。
  - 录音链路已落地：`ui/chat/stt_recorder.py` 使用 Qt 麦克风输入采集 PCM，支持静音检测、超时停止和 WAV 字节生成。
  - 主链路接入已落地：聊天窗麦克风按钮可启动录音、进入转写 worker，识别文本回到 `_on_send()`，复用 Agent、SessionContext、日志与 TTS 管线；关闭窗口时会治理 recorder 与 worker 生命周期；识别超时会释放当前 UI 状态并记录平台日志，迟到结果会被忽略。
  - 聊天窗线程生命周期已补强：LLM 逻辑完成不再提前释放 QThread 引用，关闭窗口时会统一请求 LLM / STT / TTS / 翻译 / 参考预热线程停止并等待收口。
  - 系统页已改为基础外观、聊天显示、被动状态、被动气泡、视觉 / OCR、网络六组；字体控件使用带字体预览的系统字体下拉框；系统页独立显示 `保存系统配置`，只保存系统配置，保存成功后应用到已打开聊天窗，保存失败会回滚内存配置、设置页草稿和已打开聊天窗配置。
  - 当前边界：相关自动化测试曾覆盖配置、设置页、被动状态、录音状态、适配器和聊天窗主链路；真实麦克风、真实 faster-whisper 模型转写和真实 STT / TTS 互锁由后续实机联调验证。
- 第六阶段：实现完成，本地自动化验证和 sub agent 复审通过，实机验收暂缓
  - 插件 / MCP 管理增强已接入：插件加载状态、MCP 连接诊断、工具来源名称、HTTP 请求超时和重试配置。
  - 实机评审第一批收口已接入：MCP 新增 / 编辑弹窗覆盖连接超时、请求超时和失败重试；角色核心文件从 UI 删除路径加硬保护；STT 禁用、忙碌和麦克风启动失败会进入聊天运行状态条；平台日志文案与导出名称已统一。
  - 浏览器持续会话已接入：`web_automation` 支持 `web_session_open`、导航、等待、提取、点击、填写、状态和关闭；持续会话由 Playwright 控制，不复用系统默认浏览器窗口。
  - OCR 与视觉输入已接入：新增 `vision/` 模块，默认使用 RapidOCR，支持 PaddleOCR 进阶可选后端、显式读屏触发和 `SessionContext.visual_observations` 注入。
  - 启动窗口、插件 / MCP 页面拆分、设置中心字体与滚轮治理、平台日志来源配色等第六阶段 UI 改进已完成本地验证。
  - 产品级收口已补充：
    - 聊天窗新增运行状态条，覆盖思考、读屏、回复、语音合成、失败重试和打开平台日志；发送按钮在忙碌态承担停止当前生成语义
    - 流式回复显示按短间隔合帧刷新，减少每个 chunk 触发完整富文本重绘；TTS 句段提交仍按原链路即时推进
    - 立绘管理器缓存原图和近期缩放结果，降低滚轮缩放和情绪切换时重复读图 / 平滑缩放成本
  - 运行期中间产物目录 `data/browser_sessions/` 与 `data/vision/` 默认不提交。

## 下一步

- 暂缓实机验收，后续恢复时优先检查：
  - 真实麦克风、真实 faster-whisper 模型、真实 STT / TTS / API 场景联调
  - 真实 Playwright Edge 持续会话、真实 RapidOCR / PaddleOCR 环境、第三方 MCP 服务端联调
  - 平台日志补做真实 API / TTS / STT / 浏览器 / OCR 异常场景的全面联调验证

## 文档入口

- [文档入口](./docs/README.md)
- [代码架构](./docs/architecture.md)
- [UI 规范](./docs/ui-guidelines.md)
- [插件与 MCP](./docs/plugin-mcp.md)
- [OCR 与视觉输入](./docs/vision-ocr.md)
- [开发流程](./docs/development.md)
- [服务端 TTS 对接规范](./docs/service-tts-compatibility.md)
