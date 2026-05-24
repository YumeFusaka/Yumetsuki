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

## 规划文档

- 路线图设计：
  - `docs/superpowers/specs/2026-05-24-phase-4-6-roadmap-design.md`
- Phase 5 / 6 设计：
  - `docs/superpowers/specs/2026-05-24-phase-5-ui-stt-design.md`
  - `docs/superpowers/specs/2026-05-24-phase-6-browser-vision-ecosystem-design.md`
- 当前新增设计：
  - `docs/superpowers/specs/2026-05-24-logging-workbench-design.md`
- 当前实施计划：
  - `docs/superpowers/plans/2026-05-24-logging-workbench-implementation.md`
- 当前优先级：
  1. 日志工作台：对话日志 / 系统日志与结构化持久化
  2. Phase 5：桌宠体验与交互输入输出
  3. Phase 6：高级代理、插件生态与视觉

说明：

- Phase 4 已完成，当前不再需要继续把所有设计与实施优先绑定到 Phase 4 收口
- 日志工作台是后续 Phase 5 / 6 排障与可观测性的推荐前置项
- 已完成并被主文档吸收的 Phase 4 细分 spec / plan 应及时删除，避免入口持续指向历史收口材料
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
- `data/config/system_config.yaml`
  系统配置
- `data/config/mcp.yaml`
  MCP 实际配置
- `data/config/mcp.example.yaml`
  MCP 示例模板
- `data/config/memory.yaml`
  记忆配置
  含本地模型路径，不应提交
- `data/config/agent.yaml`
  Agent 默认配置
  当前已包含 `session_context`、`tts_runtime` 两组运行时配置
  可提交默认值，但个人临时调参不应随意提交

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
- 以下类型默认都应朝配置化方向演进：
  - 短期记忆窗口、衰减、摘要预算
  - TTS 超时、并发、回退、队列长度
  - STT 录音与静音阈值
  - 被动互动频率、停留时长、显示策略
  - 浏览器自动化超时、OCR 频率、事件刷新频率

### 对 spec / plan 的要求

- spec 中如出现参数数值，必须明确其属于：
  - 示例值
  - 建议默认值
  - 或未来配置项候选
- plan 中如果展示示例代码，不应默认把关键参数直接写死为字面量，应尽量体现“由配置读取”的实现方向

## Git 约定

- 不提交真实 API key
- 不提交个人本地配置变更，除非明确需要
- 不提交 `data/models/`（向量模型目录）
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
- Agent 日志相关改动优先覆盖事件发布与日志页入口逻辑
- `EventBus` 相关改动优先覆盖：
  - 发布时 handler 快照语义
  - 订阅 / 退订与发布并发下的基本安全性
  - `UIEventBridge` 的主线程批量刷新与日志顺序
- UI 变更至少保证：
  - 行为测试
  - `py_compile`
  - 必要时 Qt offscreen 实例化
  - 聊天窗缩放 / 滚动类调整优先补回归测试
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
- TTS：
  - `python -m pytest tests/test_tts_pipeline.py tests/test_tts_adapter.py tests/test_chat_tts_flow.py -q`
- 语法检查：
  - `python -m py_compile core/event_bus.py core/ui_event_bridge.py ui/settings/pages/agent_page.py ui/chat/tts_pipeline.py ui/chat/window.py tts/adapters/gptsovits.py`

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

- 只有 API 页面显示 `保存配置`
- 点击后需确认
- 只保存 API 配置
- 切页即放弃未保存编辑

### 系统页面

- 不显示保存按钮
- 配置实时写入

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
