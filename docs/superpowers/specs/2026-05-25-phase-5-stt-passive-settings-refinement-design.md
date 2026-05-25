# Phase 5 改进：faster-whisper、本地被动状态与系统设置设计

日期：2026-05-25

> 状态：设计已确认，等待实施计划。

## 背景

Phase 5 已完成显示配置、被动气泡、STT 录音与转写主链路的基础闭环，但当前实现仍有几处方向偏差：

- STT 默认围绕 `openai_whisper` / OpenAI SDK 设计，不符合本项目优先接入本地能力的方向。
- 被动气泡被做成系统设置里的开关，而不是桌宠运行态。
- 系统设置外观区域过于拥挤，且仍使用文本框填写字体。
- 系统设置缺少与 API 页面隔离的保存按钮和保存后应用逻辑。

本设计用于修正这些偏差，使 Phase 5 更贴近桌宠运行体验。

## 目标

- 将 STT 收敛为本地 faster-whisper 服务接口。
- 删除 `openai_whisper` 适配路径，不做兼容保留。
- 将“被动互动”改为聊天窗运行状态：
  - 用户空闲超过阈值自动进入被动状态。
  - 右键菜单可手动进入或退出被动状态。
  - 被动状态下主动消息使用气泡输出。
- 重排系统设置外观区域，降低拥挤感。
- 字体选择使用系统字体下拉框。
- 系统页拥有独立保存按钮，只保存系统配置；保存后立即应用到已打开的聊天窗。

## 非目标

- 不在本轮实现项目内直接加载 faster-whisper 模型。
- 不在本轮处理模型下载、GPU 设备选择或 compute type。
- 不保留 OpenAI Whisper 兼容路径。
- 不重做设置中心整体视觉结构。
- 不新增复杂的状态动画或角色动作系统。

## STT 设计

### 配置模型

`ASRConfig` 只保留本地服务调用所需字段：

- `engine`: 默认 `"faster_whisper"`，可为 `"none"` 禁用。
- `api_url`: faster-whisper 本地服务地址，默认建议为 `http://127.0.0.1:8000`。
- `model`: 模型名或服务端识别的模型标识。
- `language`: 语言代码，允许 `zh`、`ja`、`en`、`ko`、`yue`、`auto`。
- `record_timeout_seconds`
- `silence_threshold`
- `silence_duration_ms`

移除或不再使用：

- `base_url`
- `api_key`
- `model_path`
- `openai_whisper`
- OpenAI SDK 适配器

### 本地服务协议

`FasterWhisperAdapter` 通过 HTTP 调用本地服务：

```text
POST {api_url.rstrip("/")}/transcribe
Content-Type: multipart/form-data

file: speech.wav
model: <ASRConfig.model>
language: <ASRConfig.language>
```

服务返回 JSON：

```json
{
  "text": "识别文本",
  "language": "zh"
}
```

适配器行为：

- 录音为空时返回 `STTResult(text="", error="录音内容为空")`。
- HTTP 请求异常、非 2xx、JSON 缺失 `text` 时返回可展示错误。
- 成功时去除文本首尾空白，返回 `STTResult(text=..., language=...)`。
- `STTManager` 只识别 `"none"` 与 `"faster_whisper"`；其他值返回“不支持的 STT 引擎”错误。

## 被动状态设计

### 状态定义

聊天窗新增运行态：

- 主动状态：用户正在正常使用桌宠，主动消息显示在主对话框。
- 被动状态：桌宠处于陪伴/待机形态，主动消息显示为独立气泡。

被动状态不是系统级开关，不放在系统设置里。

### 自动进入

系统配置保留被动状态阈值：

- `passive_interaction.idle_threshold_seconds`
  - 默认 `300`
  - 设置页显示为“空闲进入被动状态”，单位分钟或秒均可，但落盘统一为秒。

聊天窗维护用户交互时间：

- 用户发送文本
- 点击麦克风
- 录音开始或停止
- 拖动窗口
- 滚轮缩放
- 打开设置
- 右键菜单操作

这些操作会刷新最后交互时间，并让聊天窗退出被动状态。

当空闲时间达到阈值，聊天窗自动进入被动状态。

### 手动切换

聊天窗右键菜单新增状态操作：

- 主动状态显示：`进入被动状态`
- 被动状态显示：`退出被动状态`

手动进入后立即切换为被动状态。

手动退出后刷新最后交互时间，避免刚退出又被自动空闲检测重新切入。

### 主动消息输出

`_on_proactive_message()` 根据当前运行态决定输出：

- 被动状态：调用被动气泡显示。
- 主动状态：沿用主对话框显示。

用户主动发送消息时：

- 隐藏被动气泡。
- 退出被动状态。
- 按既有 `_on_send()` 主链路处理。

## 系统设置设计

### 页面结构

系统设置页拆分为更清晰的区域：

- 基础外观
  - 语言
  - 主题
  - 字体
  - 字号
- 聊天显示
  - 聊天字号倍率
  - 气泡缩放
- 被动状态
  - 空闲进入被动状态阈值
  - 气泡最大宽度
  - 气泡停留时长
- 网络
  - HTTP 代理

各组之间增加垂直间距，表单行距高于当前实现，避免控件上下挤压。

### 字体选择

字体控件改为 `QComboBox`：

- 使用 `QFontDatabase.families()` 获取系统字体。
- 当前配置字体存在时选中该字体。
- 当前配置字体不存在时插入配置值并选中，避免旧配置丢失。
- 字体下拉框可编辑，以便用户手动输入未被 Qt 枚举到的字体名。

### 保存语义

设置中心底部保存按钮在以下页面显示：

- API 页面：保存 API 配置。
- 系统页面：保存系统配置。

保存按钮文案可根据当前页面切换：

- API 页面：`保存 API 配置`
- 系统页面：`保存系统配置`

系统页不再实时保存。用户切离系统页时不自动保存，未保存编辑保持在控件中直到用户保存、关闭或重置窗口。

系统页保存流程：

1. `SystemPage.apply()` 写入 `ConfigManager.system`。
2. `ConfigManager.save_system()` 持久化。
3. 若聊天窗已打开，调用聊天窗公开方法应用新的系统配置。
4. 显示保存成功反馈。

保存后立即应用范围：

- 聊天字体、字号和倍率。
- 气泡缩放、最大宽度、停留时长。
- 被动空闲阈值。
- 已显示的被动气泡需要重新定位和重算宽度。

## 交互与数据流

### STT 数据流

```text
麦克风按钮
→ STTRecorder 录音
→ WAV bytes
→ STTTranscribeWorker
→ STTManager
→ FasterWhisperAdapter
→ 本地 faster-whisper 服务
→ STTResult
→ ChatWindow._on_stt_result()
→ ChatWindow._on_send()
```

### 被动状态数据流

```text
用户交互
→ refresh_interaction()
→ 退出被动状态
→ 空闲计时器继续检测

空闲阈值达到
→ 进入被动状态

ProactiveScheduler 主动消息
→ ChatWindow._on_proactive_message()
→ 被动状态：气泡
→ 主动状态：主对话框
```

### 系统保存数据流

```text
系统页控件
→ 保存系统配置
→ ConfigManager.save_system()
→ SettingsWindow 通知已打开 ChatWindow
→ ChatWindow.apply_system_config()
→ 重新应用字体、缩放、气泡和空闲阈值
```

## 错误处理

- faster-whisper 服务不可达：输入框提示“识别失败：...”。
- 返回 JSON 不合法：输入框提示“识别失败：本地 STT 服务返回格式无效”。
- `text` 为空：输入框提示“没有识别到语音”。
- 系统字体枚举失败：字体下拉框至少包含当前配置值和默认字体。
- 保存系统配置失败：弹出保存失败反馈，不修改已打开聊天窗运行配置。

## 测试策略

新增或更新测试覆盖：

- `ASRConfig` 默认引擎为 `faster_whisper`。
- API 页 ASR 引擎只有 `none` 与 `faster_whisper`。
- `STTManager` 对 `faster_whisper` 创建本地服务适配器。
- `FasterWhisperAdapter` 正确发送 multipart 请求并解析 JSON。
- `openai_whisper` 不再作为可用选项。
- 聊天窗右键菜单包含被动状态切换动作。
- 空闲阈值达到后进入被动状态。
- 用户发送、麦克风、打开设置等交互退出被动状态。
- 被动状态下主动消息使用气泡，主动状态下使用主对话框。
- 系统页字体控件使用系统字体下拉框。
- 系统页保存按钮只保存系统配置，不保存 API 配置。
- 系统页保存后应用配置到已打开聊天窗。
- 系统设置布局组拆分后仍保留全部原有配置项。

## 验收标准

- 默认 STT 引擎为 `faster_whisper`，且本地服务接口可完成一次离线 mock 转写测试。
- 代码中不再存在 `openai_whisper` 适配器或设置页选项。
- 用户空闲达到配置阈值后自动进入被动状态。
- 右键菜单可手动进入和退出被动状态。
- 只有被动状态下的主动消息使用气泡。
- 系统设置外观相关控件不再集中挤在单个表单组中。
- 字体通过系统字体下拉框选择。
- API 页和系统页保存语义隔离。
- 系统页保存后，已打开聊天窗立即应用新外观和被动状态参数。
