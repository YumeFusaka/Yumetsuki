# TTS 自动播报接入设计

## 背景

当前项目已经具备：

- API 设置页中的 TTS 配置项
- `tts/adapters/gptsovits.py` 中的 GPT-SoVITS HTTP 适配器

但聊天主链路没有实例化 TTS 适配器，也没有在回复完成后触发语音合成和本地播放，因此即使 GPT-SoVITS 服务正常运行，用户也不会听到语音。

本设计的目标是在不改动 `LLMManager` / `AgentManager` 职责边界的前提下，为聊天窗口补齐“流式出字时句级增量播报”的最小闭环。

## 目标

- 启动聊天窗口时将 TTS 配置注入聊天层
- 当角色回复流式生成时，按句级边界切分并尽早触发 TTS
- 成功拿到音频后按原句顺序连续播放
- TTS 失败时不影响文本对话
- 为失败场景提供最小可见日志，避免静默失败

## 非目标

- 不实现真正的音频流式推理
- 不在本次接入中支持多个 TTS 提供商的完整插件化扩展
- 不增加新的设置页交互项
- 不改动 Agent / LLM 的核心消息生成逻辑

## 方案选择

采用“聊天窗内挂接轻量句级 TTS 管线”的方案。

理由：

- TTS 属于输出表现层，更适合放在 `ChatWindow` 附近，而不是塞回 `LLMManager` 或 `AgentManager`
- 当前聊天窗已经接收流式文本块，具备在 UI 层做句级切分和顺序播放的天然接入点
- 改动范围小，便于后续逐步扩展为更细粒度的分段策略、播报开关或取消机制

## 组件设计

### 1. `SettingsWindow` 配置透传

`SettingsWindow._launch_chat()` 在创建 `ChatWindow` 时，除现有 `self._config.api.llm` 外，再传入 `self._config.api.tts`。

职责：

- 只负责把配置传递到聊天窗口
- 不承担任何 TTS 初始化或播放逻辑

### 2. `ChatWindow` 中的句级 TTS 生命周期

`ChatWindow` 新增：

- 可选 `tts_config` 构造参数
- `_tts_adapter` 字段
- `_streamed_assistant_text` 字段，用于记录当前轮次已显示的完整 assistant 文本
- `_tts_pending_buffer` 字段，用于积累尚未送入 TTS 的尾部文本
- `_current_utterance_id` 字段，用于区分对话轮次
- `_next_segment_id` / `_next_play_id` 字段，用于管理句子顺序
- `_segment_results` 字段，用于缓存已合成完成但尚未轮到播放的音频
- `_active_tts_workers` 字段，用于管理后台合成线程

初始化规则：

- `tts.engine == "gptsovits"` 时创建 `GPTSoVITSAdapter`
- `tts.engine == "none"` 或未知引擎时，不创建适配器

触发规则：

- 每次用户发送消息后，递增 `utterance_id`，并清空当前轮次的句级缓冲与排序状态
- 每次 `_on_chunk()` 收到新的 `ProcessedText` 时，计算相对上一次文本的新增部分，追加到 `_tts_pending_buffer`
- 每次追加后，对缓冲区执行句级切分；只在 `。！？；` 或换行边界切出完整句子
- 被切出的句子立即进入后台 TTS 合成队列，不等待整轮回复结束
- `_on_llm_done()` 时，如果缓冲区中仍有未闭合尾段，则强制 flush 为最后一个片段并送入 TTS
- `，` 不作为切分边界，优先保证单句语音自然度

可选优化：

- 为极短句设置最小长度门槛，例如 4 到 6 个字符，避免“嗯。”“好。”一类片段过于频繁触发 TTS
- 该门槛先实现为代码常量，不进入设置页

### 3. 后台 TTS Worker 与片段调度

新增一个轻量 `QThread` Worker，仅负责：

- 接收单个句子片段文本
- 接收所属 `utterance_id` 和 `segment_id`
- 调用 `adapter.synthesize(text)`
- 通过信号返回音频字节或错误消息

不在 UI 线程直接发 HTTP 请求，避免主线程卡顿。

调度策略：

- 每个被切出的句子分配递增的 `segment_id`
- TTS 合成允许并发或准并发执行，但播放必须严格按 `segment_id` 顺序进行
- 如果后一句先合成完成，只缓存结果，不允许抢先播放
- 新一轮用户输入开始后，上一轮未播放和未完成合成的片段全部作废

### 4. 本地音频播放

使用 Qt 多媒体播放内存中的音频字节，优先保持项目依赖收敛：

- `QMediaPlayer`
- `QAudioOutput`
- `QBuffer`

播放模型：

- 句子级播放，按切分顺序连续播报
- 当前句在播时，后续句可继续后台合成
- 使用内存缓冲区承载返回的音频字节，不强制落盘
- 新一轮播报开始前，旧轮尚未开始的播放直接作废
- 如果播放器正播旧轮音频，收到新轮开始信号后停止旧播放并切换到新轮

如果当前 Qt 多媒体对内存源兼容性不足，再退化为写入临时文件播放；但首选内存播放。

## 数据流

```text
用户发送消息
→ LLM/Agent 正常流式生成文本
→ ChatWindow 在 `_on_chunk()` 持续刷新 UI
→ ChatWindow 提取本次 chunk 相对上次的新增文本
→ 新增文本进入 `_tts_pending_buffer`
→ 命中 `。！？；` 或换行边界时切出完整句子
→ 句子片段进入后台 TTS Worker 队列
→ Worker 调用 GPT-SoVITS HTTP API
→ 返回音频字节
→ UI 线程按 `segment_id` 顺序启动播放器播报
→ `_on_llm_done()` 时 flush 未闭合尾段
```

失败分支：

```text
TTS 未配置 / 未启用
→ 直接跳过

单句 TTS HTTP 失败 / 返回非 200 / 空音频
→ 记录失败信息
→ 该句跳过
→ 后续句子继续合成与播放

播放器初始化或播放失败
→ 记录失败信息
→ 不影响后续句子与下一轮对话

新一轮用户输入开始
→ 旧轮剩余未播放片段作废
→ 旧轮迟到的 TTS 结果忽略
```

## 错误处理

### 适配器层

调整 `GPTSoVITSAdapter`：

- 保留 `bytes | None` 返回约定，减少改动面
- 增加可诊断信息输出，不再把所有异常完全静默吞掉

最小要求：

- 非 200 时输出状态码
- 请求异常时输出异常信息

### UI 层

`ChatWindow` 的 TTS 失败只做轻量提示，不弹阻塞式对话框。

优先级：

- 开发期：控制台 / 标准输出日志
- 如现有反馈组件易复用，可考虑追加非模态 toast；但这不是本次必须项

## 并发与状态约束

- 聊天文本生成线程和 TTS 合成线程分离
- 可存在多个活跃 TTS Worker，但每个结果必须携带 `utterance_id` 和 `segment_id`
- 新回复开始时，如上一个轮次的 TTS Worker 仍未完成，不强制中断 HTTP 请求，但忽略其落后结果
- 播放器始终以最新一轮回复为准，旧音频不应覆盖新音频
- 播放顺序严格遵守 `segment_id`，不能因为后句更早合成成功而乱序

实现上使用递增的 `utterance_id` 区分轮次，使用递增的 `segment_id` 区分句子顺序。

## 测试设计

本次至少补以下测试：

1. `SettingsWindow` 启动聊天时会把 `api.tts` 传给 `ChatWindow`
2. `ChatWindow` 在流式输出中遇到 `。！？；` 或换行时会切出句子并触发 TTS
3. `，` 不会触发切句
4. 当 `tts.engine == "none"` 时不会触发 TTS
5. 无结尾标点时会在 `_on_llm_done()` 时 flush 尾段
6. 后生成的片段先合成完成，也不能抢先播放
7. 新一轮输入开始后，上一轮残留片段会失效
8. 单句 TTS 返回 `None` 或报错时，不影响文本显示和后续句子
9. `GPTSoVITSAdapter` 失败时仍保持可预测返回值

测试策略：

- 单元测试优先 mock `requests.post`
- UI 测试避免真实音频播放，替换播放器对象或播放方法
- 不依赖真实 GPT-SoVITS 服务进程

## 影响文件

预计涉及：

- `ui/settings/window.py`
- `ui/chat/window.py`
- `tts/adapters/gptsovits.py`
- `tests/test_tts_adapter.py`
- 新增一个聊天窗 TTS 切分与调度测试文件

## 验收标准

- 在 `data/config/api.yaml` 中启用 `gptsovits` 且服务可访问时，角色首个完整句生成后即可开始播报
- 句子切分只基于 `。！？；` 和换行，不基于 `，`
- 多句回复按文本顺序连续播报，不允许后句抢先
- GPT-SoVITS 不可用时，文本回复仍正常显示，不会卡死 UI
- 新增测试通过
- 文档同步更新 `CLAUDE.md` 和 `docs/` 中相关说明
