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
  可提交默认值，但个人临时调参不应随意提交

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
- Agent 日志相关改动优先覆盖事件发布与日志页入口逻辑
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
  - `ui/chat/audio_backends.py` 中 WAV / PCM 播放后端的无真实设备测试
  - 拟声词、语气词、拖长音、重复音节在翻译时优先保留音感，不被语义意译破坏
  - 避免依赖真实 GPT-SoVITS 服务或真实音频设备

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
