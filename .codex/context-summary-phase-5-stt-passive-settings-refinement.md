## 项目上下文摘要（Phase 5 STT / 被动状态 / 系统设置改进实现）

生成时间：2026-05-25 20:16:42 +08:00

### 1. 相似实现分析

- **实现1**: `ui/settings/pages/api_page.py`
  - 模式：设置页持有配置对象，控件通过 `apply()` 写回，`reset()` 从配置恢复。
  - 可复用：TTS 本地服务 URL、语言下拉框、RoseSpinBox 数值控件。
  - 需注意：API 页保存由 `SettingsWindow._apply_and_save_api()` 统一落盘，页面自身不保存。
- **实现2**: `ui/settings/pages/system_page.py`
  - 模式：系统设置页直接编辑 `SystemConfig` 的显示、网络和运行参数。
  - 可复用：`QGroupBox + QFormLayout` 分组布局、`SAKURA_COMBO_BOX_STYLE` 下拉框样式。
  - 需注意：本轮改为非实时保存，页面只负责 `apply()` 写内存配置。
- **实现3**: `ui/chat/window.py`
  - 模式：`ChatWindow` 是输入、STT、主动消息、TTS 和显示状态的集成点。
  - 可复用：`_show_passive_bubble()`、`_hide_passive_bubble()`、`_apply_scale()`、`_on_send()` 主链路。
  - 需注意：被动状态只能影响主动消息展示，不应绕过 `_on_send()`、Agent、SessionContext 或 TTS 管线。
- **实现4**: `stt/manager.py`、`stt/adapter.py`
  - 模式：`STTManager` 根据 `ASRConfig.engine` 创建适配器，未知引擎返回可展示错误。
  - 可复用：`STTAdapter.transcribe_wav()` 与 `STTResult` 数据协议。
  - 需注意：本轮只保留 `none` 与 `faster_whisper`，`openai_whisper` 作为不支持引擎返回错误。

### 2. 项目约定

- **命名约定**: PySide 控件实例使用 `_xxx` 私有字段；测试函数使用 `test_行为描述`。
- **文件组织**: 配置模型在 `config/schema.py`；设置页在 `ui/settings/pages/`；聊天窗集成在 `ui/chat/window.py`；STT 适配器在 `stt/adapters/`。
- **导入顺序**: 标准库、第三方库、项目内模块分段；现有文件未强制自动排序。
- **代码风格**: 4 空格缩进，PySide 信号连接集中在构造阶段，测试通过 monkeypatch 隔离真实 Qt worker、LLM 和服务端。

### 3. 可复用组件清单

- `config.schema.ASRConfig`: STT 配置来源。
- `config.schema.SystemConfig`: 系统设置、聊天显示和被动状态配置来源。
- `ui.widgets.rose_spin_box.RoseSpinBox`: 设置页数值输入。
- `ui.theme.SAKURA_COMBO_BOX_STYLE`: 设置页下拉框主题。
- `stt.adapter.STTAdapter`: STT 适配器抽象。
- `stt.types.STTResult`: STT 转写结果协议。
- `ui.chat.window.ChatWindow._show_passive_bubble()`: 被动气泡展示。
- `ui.chat.window.ChatWindow._apply_scale()`: 聊天窗字体、按钮、气泡尺寸统一应用入口。

### 4. 测试策略

- **测试框架**: pytest。
- **测试模式**: 配置单元测试、设置页控件测试、STT HTTP mock 测试、聊天窗状态机测试。
- **参考文件**:
  - `tests/test_config.py`
  - `tests/test_settings_window.py`
  - `tests/test_stt_adapter.py`
  - `tests/test_chat_passive_bubble.py`
  - `tests/test_chat_window_scale.py`
- **覆盖要求**: 默认值、保存/重置、未知引擎错误、HTTP 成功与异常、空音频、被动状态进入/退出、系统配置应用到已打开聊天窗。

### 5. 依赖和集成点

- **外部依赖**: PySide6、requests、pytest、Pydantic。
- **内部依赖**:
  - `SettingsWindow -> APIPage/SystemPage -> ConfigManager`
  - `ChatWindow -> STTRecorder -> STTManager -> FasterWhisperAdapter`
  - `ChatWindow -> SystemConfig.chat_display/passive_interaction`
- **集成方式**: STT worker 使用 Qt Signal 回主线程；系统页保存后通过 `ChatWindow.apply_system_config()` 应用运行态配置。
- **配置来源**: `data/config/api.yaml` 的 `asr`；`data/config/system_config.yaml` 的 `chat_display` 与 `passive_interaction`。

### 6. 技术选型理由

- **为什么用本地 HTTP faster-whisper**: 用户明确要求不再兼容 OpenAI Whisper，并参考 TTS 一样接入本地地址接口。
- **优势**: 复用现有适配器层，离线测试可通过 mock HTTP 覆盖，真实服务替换成本低。
- **劣势和风险**: 真实 faster-whisper 服务的 multipart 字段和错误格式仍需本地联调确认。

### 7. 关键风险点

- **并发问题**: STT worker、TTS worker、Qt 定时器关闭顺序需继续通过关闭路径测试覆盖。
- **边界条件**: 空音频、本地服务异常、返回 JSON 缺失 `text`、旧配置中遗留 `openai_whisper`。
- **性能瓶颈**: 本地 HTTP 转写会阻塞 worker 线程，不阻塞 UI 主线程。
- **安全考虑**: 本轮未新增认证、鉴权或加密逻辑；本地配置文件仍不提交。
