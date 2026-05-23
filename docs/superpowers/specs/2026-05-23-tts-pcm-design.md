# TTS PCM 低延迟模式设计

日期：2026-05-23

> 状态：客户端侧实现已完成。
>
> 说明：本设计稿覆盖的桌宠端改动已经落地，包括 `audio_mode`、流式事件抽象、PCM 播放后端、保底模式 / 音频扩展 / 会话扩展边界，以及会话级 WAV 回退。
> 当前进一步确认的剩余异常（如服务端 warmup 文本语言选择错误、服务端内部切句产生 `、。`）归因服务端，不再视为本仓库当前未完成事项。

## 背景

当前 Yumetsuki 的句级 TTS 管线已经支持：

- GPT-SoVITS HTTP 合成
- 按句硬断句与长句软切分
- 逐句翻译后播报
- 参考音频预热、自动回退与服务端托管参考
- 按句顺序播放与单句失败跳过

现有播放链路位于 [ui/chat/window.py](../../../../ui/chat/window.py)，采用 `QMediaPlayer + QBuffer`，默认把 TTS 返回值视为一段完整的可解码音频文件字节流。该模型适合 `wav/mp3/ogg` 等容器格式，但不能满足“服务端持续推送裸 PCM、客户端边收边播”的低延迟需求。

本次设计目标是在不破坏现有 WAV 兼容链路的前提下，引入真正的 PCM 流式低延迟模式，并在设置界面中提供用户可选的音频模式。

## 目标

- 在设置页新增 TTS 音频模式：
  - 自动（推荐）
  - PCM流式（低延迟）
  - WAV（兼容/调试）
- 当用户选择 PCM 流式时，客户端按流式方式消费服务端返回的裸 PCM 数据，并尽快首播
- 当用户选择 WAV 时，保留现有“等待整段音频完成后播放”的兼容行为
- 当用户选择自动时，优先尝试 PCM 流式；若失败，则在当前聊天会话内回退为 WAV，避免每句重复试错
- 与现有句级顺序播放、逐句翻译、参考音频预热和单句失败跳过逻辑兼容
- 为服务端“speaker 会话化”预留明确协议边界

## 非目标

- 不修改句级切分与逐句翻译的核心策略
- 不在本次设计中引入新的 TTS 引擎
- 不把一次运行中的临时回退状态写回持久化配置
- 不删除现有 WAV 路径
- 不依赖真实音频设备或真实 GPT-SoVITS 服务做自动化测试

## 兼容性前提

- 原版 GPT-SoVITS 兼容是最高优先级，桌宠端魔改协议只能作为增量扩展
- 服务端对桌宠端的支持必须通过显式扩展字段、可选行为或向后兼容的新增响应信息实现
- 禁止为了兼容桌宠端而修改原版默认参数、原版必填项或原版返回格式
- 未显式携带扩展字段（如 `session_id`）的请求，必须保持原版行为不变

## 历史说明

- 本文档形成于服务端正式兼容规范单独收口之前，当前应以 [服务端 TTS 对接规范](../../service-tts-compatibility.md) 为最高优先级
- 若本文中任何探索性方案与正式规范冲突，一律以正式规范为准
- 当前对接决策是：优先适配原版接口；涉及桌宠端差异时，仅允许做参数、设置项和已文档化显式扩展协商，不得把新逻辑主线默认化

## 用户可见行为

### 设置页

在 API 设置页的 TTS 分组内新增“音频模式”下拉框，选项如下：

- 自动（推荐）
- PCM流式（低延迟）
- WAV（兼容/调试）

该配置持久化到 `APIConfig.tts`，与 `engine`、`api_url`、`reference_mode`、`prompt_lang`、`output_lang`、`prompt_text` 一样遵循现有保存语义：

- API 页面编辑后只有点击“保存配置”才写回
- 切换页面时未保存编辑会被丢弃

### 聊天播报

- PCM流式：
  - 优先降低首包和首播延迟
  - 服务端持续推送 PCM chunk
  - 客户端在收到首批可播放 chunk 后立即开始播放
- WAV：
  - 保持当前完整音频文件式播放行为
  - 兼容优先，便于调试
- 自动：
  - 先尝试 PCM流式
  - 如果出现格式不支持、流式不可用、首包超时、播放端无法消费 PCM 等情况，则回退到 WAV
  - 一旦某次回退成功，当前聊天窗会话剩余句段直接走 WAV，不再逐句先试 PCM

## 服务端协议设计

### 总原则

服务端采用“原版兼容优先 + 显式扩展触发”的策略，而不是为了桌宠端全局改写原版默认行为。

含义如下：

- 未显式携带扩展字段（如 `session_id`）的请求，继续保持原版 `media_type=wav`、`streaming_mode=False` 等默认语义
- 桌宠端需要 PCM 低延迟链路时，应显式传 `media_type=raw` 与 `streaming_mode=3`
- 当客户端显式传 `media_type=wav` 时，服务端必须尊重，不得强制改回 `raw`
- 当客户端显式传 `streaming_mode=0` 时，服务端必须尊重，不得强制改回流式
- 若服务端希望对桌宠端扩展路径做默认补全，也只能限定在“请求已显式携带 `session_id` 且缺少对应扩展字段”的前提下，且不得影响无 `session_id` 的原版请求

这样可以同时满足：

- PCM流式 用户拿到最大低延迟收益
- WAV 用户保留稳定兼容路径
- 自动模式 用户优先尝试低延迟，再按客户端状态机保底回退

### speaker 会话化

服务端显式引入 `session_id` 作为参考音频与 speaker 默认状态的可选会话键。

接口约定：

- `/set_refer_audio`
  - 保持兼容现有 `GET /set_refer_audio?refer_audio_path=...` 调用方式
  - 可选接收 `session_id`
  - 把 `refer_audio_path`、`prompt_lang`、`prompt_text` 等参考信息绑定到该 `session_id`
- `/tts`
  - 可选接收 `session_id`
  - 当客户端没有在本次请求中显式传 `ref_audio_path` 等字段时，服务端先尝试读取该 `session_id` 绑定的默认 speaker / 参考信息

不依赖 cookie、HTTP keep-alive 状态或进程内隐式全局变量来识别调用方会话。
未携带 `session_id` 的请求继续走原版逐次显式传参考字段的模式。

### 模式映射

客户端与服务端的请求参数映射如下。

#### PCM流式（低延迟）

- `media_type=raw`
- `streaming_mode=3`
- `text_split_method=cut5`
- `batch_size=1`
- `parallel_infer=false`
- `split_bucket=false`
- `overlap_length=2`
- `min_chunk_length=12`

适用目标：

- 尽快拿到首包
- 一边接收一边播放

#### WAV非流式（兼容/调试）

- `media_type=wav`
- `streaming_mode=0`
- `text_split_method=cut5`
- `batch_size=1`
- `parallel_infer=true`
- `split_bucket=true`
- `overlap_length=2`
- `min_chunk_length=16`

适用目标：

- 等待完整音频
- 兼容优先
- 调试友好

#### 自动模式

- 仅当服务端已显式声明支持对应扩展协商，且当前请求明确进入扩展路径时，第一选择才按 PCM流式 参数发起
- 若出现格式不支持、流式失败、首包超时、播放端无法消费或明确的服务端错误，则客户端回退到 WAV非流式
- 一次回退成功后，当前聊天会话内暂存为 WAV

### 流式返回要求

当 `media_type=raw` 时：

- 返回真正的 PCM chunked stream，而不是等整段音频生成完再一次性输出
- 首包应尽可能包含最早可播音频数据
- 服务端内部缓冲阈值应与低延迟参数目标一致，避免客户端虽按流式消费，但首包仍被服务端长时间攒住
- 必须返回稳定音频格式元数据（如 `X-Audio-Sample-Rate`、`X-Audio-Channels`、`X-Audio-Sample-Width`），避免客户端猜测 PCM 参数

当 `media_type=wav` 时：

- 保持现有完整 WAV 响应行为

### 错误语义

服务端应尽量返回稳定、可识别的错误类型，便于客户端区分“需要回退为 WAV”和“普通合成失败”：

- 参数不支持：`400`
- 流式模式不可用：`409` 或明确错误码
- `session_id` 对应参考未准备好：`400`
- 推理或首包超时：`504` 或明确超时错误

错误正文中应保留原版 `message` 语义，并可增量增加 `error_type`、`detail` 等字段；避免为了扩展支持而破坏原版错误格式。

## 客户端配置设计

### 配置结构

在 `config/schema.py` 的 `TTSConfig` 中新增字段，例如：

- `audio_mode: str = "auto"`

允许值：

- `auto`
- `pcm_stream`
- `wav`

### 设置页

在 [ui/settings/pages/api_page.py](../../../../ui/settings/pages/api_page.py) 的 TTS 分组新增音频模式下拉框，风格与现有参考模式下拉保持一致。

需要覆盖：

- 默认值显示
- apply 写回配置
- reset 还原配置
- 保存后重新打开设置页可见持久化值

## 客户端运行态设计

### 配置态与会话态分离

客户端把音频模式拆成两层：

- 配置态
  - 来自设置页
  - 表达用户偏好
  - 会持久化
- 会话态
  - 仅存在当前聊天窗实例
  - 记录自动模式是否已经降级到 WAV
  - 不持久化

自动模式的会话态建议如下：

- `prefer_pcm`
  - 默认状态
  - 当前句优先尝试 PCM流式
- `forced_wav_for_session`
  - 一次 PCM 失败并且 WAV 回退成功后进入
  - 当前聊天窗剩余句段直接使用 WAV

新的聊天窗实例重新回到 `prefer_pcm`。

### session_id 生命周期

聊天窗可以维护一个稳定的 TTS `session_id` 运行态，但不得把它视为默认前置条件。

用途：

- 仅当服务端已显式声明支持该扩展时，才在启动后异步调用 `/set_refer_audio` 预热该 `session_id`
- 仅当服务端已显式声明支持该扩展时，才在逐句 `/tts` 请求中复用同一 `session_id`
- 让服务端能够在不重复上传参考的情况下复用 speaker 会话

该 `session_id` 仅用于扩展能力协商；若服务端不支持该扩展，客户端仍需能回退到原版逐次显式传参考字段的工作流。

## TTS 适配器设计

### 当前问题

当前 `TTSAdapter` 接口为：

- `synthesize(text) -> bytes | None`

该接口只适合“返回完整音频字节流”的模型，无法表达：

- 流式开始
- 流式 chunk
- 流式结束
- 音频格式元数据

### 新抽象

建议引入显式的流式事件模型。

#### 音频格式对象

新增 `TTSAudioFormat`，至少包含：

- `transport`
  - `wav`
  - `pcm_stream`
- `sample_rate`
- `channels`
- `sample_width`

#### 流式事件对象

新增 `TTSStreamEvent`，字段包括：

- `kind`
  - `start`
  - `chunk`
  - `end`
  - `error`
- `format`
  - 仅 `start` 必填
- `data`
  - 仅 `chunk` 使用
- `message`
  - 仅 `error` 使用

#### 适配器接口

建议 `TTSAdapter` 升级为：

- `stream_synthesize(text: str, ...) -> Iterable[TTSStreamEvent]`

兼容思路：

- WAV 路径可以被适配为：
  - `start`
  - `chunk(完整 wav bytes)`
  - `end`
- PCM 路径则返回真正多次 `chunk`

### GPT-SoVITS 适配器

[tts/adapters/gptsovits.py](../../../../tts/adapters/gptsovits.py) 需要扩展为：

- 根据用户配置态与会话态，决定当前句使用 `pcm_stream` 还是 `wav`
- 仅在服务端已显式声明支持该扩展时，给 `/set_refer_audio` 与 `/tts` 请求带上 `session_id`
- 统一拼装两套参数映射
- 识别可回退错误
- 在自动模式下执行本句 PCM 失败 -> WAV 回退
- 在回退成功后，把会话态记为 `forced_wav_for_session`
- 对不支持 `session_id` 的原版服务端，保留逐次显式携带参考字段的兼容路径

参考预热、自动 inline 回退与进程内能力探测缓存逻辑应保留，并与 `session_id` 共存，不互相覆盖。

## 播放架构设计

### 总体原则

播放层不再把所有 TTS 结果统一视为“完整音频 bytes”，而是根据传输方式选择不同后端。

新增一个轻量播放抽象层，由聊天窗统一调度。

### WAV 播放后端

新增 `WavPlaybackBackend`：

- 继续使用现有 `QMediaPlayer + QBuffer`
- 输入为完整 WAV 字节流
- 适用于：
  - 用户显式选择 WAV
  - 自动模式已回退到 WAV

### PCM 流式播放后端

新增 `PcmStreamPlaybackBackend`：

- 使用 `QAudioSink + 自定义 QIODevice` 或等价可持续写入的 Qt 音频链路
- 接收：
  - `sample_rate`
  - `channels`
  - `sample_width`
- 对外提供：
  - 初始化流
  - `append_chunk()`
  - 标记输入结束
  - 查询是否真正播空

关键要求：

- 在收到第一批可播放 PCM chunk 后立即开始输出
- 不要求整句音频先全部到齐
- 在上游 `end` 且本地缓冲消费完后，才判定该句段播放完成

### 聊天窗顺序控制

当前 [ui/chat/window.py](../../../../ui/chat/window.py) 通过 `_segment_results[(utterance_id, segment_id)] = bytes` 和 `_next_play_id` 管理严格句序。

PCM 流式下，该模型需要升级为“按 segment 维护事件与播放状态”。

建议每个句段维护：

- `pending`
- `streaming`
- `ended`
- `failed`
- `played`

播放规则：

- 句段 `0` 一旦收到 `start` 和首个可播 `chunk`，立即开始播放
- 句段 `1` 即使先生成出数据，也只能先缓存事件，不能抢播
- 当前句段真正播完后，再切换到下一句段

这样既能保留“句序稳定”，也能让当前句尽早首播。

### 自动回退触发点

自动模式建议只在以下场景触发回退：

- HTTP 明确报不支持 `raw` 或 `streaming_mode=3`
- 首包超时
- `start` 事件缺失必要格式元数据
- PCM 播放后端初始化失败
- 流式过程中在任何音频播出前即报错

若已经播出部分 PCM 后中途失败：

- 不重播当前句，避免重复发声
- 当前句按失败处理
- 剩余句段切到 WAV 会话态继续进行

## 错误处理设计

### PCM 流式

- 首包超时：
  - 当前句失败
  - 自动模式切换到 `forced_wav_for_session`
- 流式中途失败且尚未播出任何 chunk：
  - 自动模式允许回退到 WAV 重试当前句
- 流式中途失败但已经播出部分内容：
  - 不重播当前句
  - 记录日志
  - 后续句段按当前会话回退策略执行

### WAV

- 保持现有语义：
  - 单句失败只跳过当前句
  - 不阻塞后续句段

### reference prepare 与 session 准备失败

- `/set_refer_audio` 失败时，不应让整个 TTS 管线直接退出
- 应继续沿用现有 inline / fallback 参考策略
- `/tts` 若返回 `session_id` 参考未准备好：
  - 自动模式可直接回退到显式 inline + WAV
  - PCM流式 或 WAV 显式模式则按普通失败处理并记录日志

### 日志字段

建议日志至少包含：

- 当前配置音频模式
- 当前会话态
- 当前句段 id
- 失败阶段
  - `prepare`
  - `first_chunk`
  - `playback_init`
  - `mid_stream`
  - `wav_request`
- 是否执行了 WAV 回退

## 测试设计

根据 [docs/development.md](../../development.md) 中对 TTS 改动的要求，本次至少补以下测试。

### 配置与设置页

- `audio_mode` 默认值、持久化、apply / reset
- 设置页下拉框选项与显示文案
- `SettingsWindow -> ChatWindow` 配置透传

### TTS 适配器

- `pcm_stream`、`wav`、`auto` 三种模式的请求参数映射
- `/set_refer_audio` 与 `/tts` 是否透传 `session_id`
- 自动模式首句 PCM 失败后是否回退 WAV
- 一次回退成功后，同一聊天窗会话是否直接走 WAV
- 保留原有 reference prepare / inline fallback / 语言别名逻辑
- 未启用 `session_id` 扩展时，是否继续兼容原版 `wav` / 非流式 / 显式参考字段路径

### 聊天窗

- PCM 句段按顺序播放，后到句段不会抢播
- 首个 PCM chunk 到达即可启动播放
- 流式中途失败但已播出部分时，不重复播放当前句
- 新用户轮次会清理旧流、旧缓冲与旧句段状态
- WAV 路径继续保持现有顺序播放语义

### 播放后端

- WAV 后端继续走 `QMediaPlayer` 路径
- PCM 后端支持连续 `append_chunk()`
- `end` 后等待缓冲区播空再发完成信号

所有测试应继续满足：

- 不依赖真实 GPT-SoVITS 服务
- 不依赖真实音频设备
- 外部依赖优先 mock

## 实施边界

建议拆为以下实现阶段：

1. 配置模型与设置页
2. TTS 适配器协议升级
3. GPT-SoVITS 请求映射与自动回退
4. PCM 流式播放后端接入
5. 聊天窗句段状态机升级
6. 测试补齐
7. 文档同步更新

## 文档更新要求

实现完成后需要同步更新：

- [CLAUDE.md](../../../CLAUDE.md)
- [docs/README.md](../../README.md)
- [docs/architecture.md](../../architecture.md)
- [docs/development.md](../../development.md)

应补充的信息包括：

- TTS 新增音频模式
- `session_id` 驱动的 speaker 会话化
- PCM 流式播放链路
- 自动模式的会话级 WAV 回退策略
- 新增测试覆盖范围
- 原版兼容优先与扩展能力显式触发原则

## 风险与取舍

- PCM 流式的收益主要来自服务端首包尽快返回与客户端可持续播放，两端任一侧仍按整句缓冲都会显著削弱收益
- 自动模式若回退判定过于激进，可能把偶发抖动误判为“服务端不支持流式”；若判定过松，则会让用户多次经历首句失败
- 引入第二套播放后端会提高聊天窗状态管理复杂度，因此必须把播放后端与句段状态机隔离，避免把 Qt 细节散落到主窗口流程里
- speaker 会话化若不使用显式 `session_id`，后续参考预热与多窗口并发会明显变脆弱

## 推荐结论

本次方案采用以下主线：

- 客户端暴露 `auto / pcm_stream / wav` 三种音频模式
- 服务端保持原版默认行为不变，仅通过显式扩展支持桌宠端协议
- 服务端引入显式 `session_id` 做可选 speaker 会话化，而不是新的默认主线
- 客户端自动模式仅在显式扩展路径已成立时优先尝试 PCM，失败后在当前聊天窗会话内锁定为 WAV
- 客户端新增独立 PCM 流式播放后端，同时保留现有 WAV 播放链路

该方案能够在不破坏现有兼容路径的情况下，为桌宠聊天窗提供真实可感知的首字延迟优化，并保留足够清晰的调试与回退边界。
