## 项目上下文摘要（Phase 5 UI 与 STT 实施计划）

生成时间：2026-05-25 16:57:32

### 1. 相似实现分析

- **实现1**: `config/schema.py`
  - 模式：Pydantic 配置模型集中声明，`APIConfig`、`SystemConfig`、`AgentConfig` 分别承载不同运行域。
  - 可复用：`ASRConfig` 已存在 `engine`、`model_path`，`SystemConfig` 已存在 `font_family`、`font_size`。
  - 需注意：关键体验参数应优先配置化，不能散落到 UI 硬编码。
- **实现2**: `ui/settings/pages/system_page.py`
  - 模式：系统配置页面实时保存，控件变化后调用 `_save_live()` 写入 `system_config.yaml`。
  - 可复用：`RoseSpinBox`、`SAKURA_COMBO_BOX_STYLE`、`ConfigManager.save_system()`。
  - 需注意：系统页面不显示“保存配置”，新增显示项应继续实时生效。
- **实现3**: `ui/chat/window.py`
  - 模式：聊天窗用 `BASE_*` 常量和 `_scale` 统一驱动字体、边框、按钮、滚动区域，TTS 通过 `TTSPipelineController` 管理句段生命周期。
  - 可复用：`_apply_scale()`、`_rebuild_stylesheet()`、`_begin_new_tts_turn()`、`_on_send()`、`_on_proactive_message()`。
  - 需注意：STT 接入必须复用现有发送入口，避免绕过 `SessionContext` 与 Agent 主链路。
- **实现4**: `agent/proactive.py`
  - 模式：后台 `QThread` 周期检查，使用 Qt `Signal` 回主线程展示主动消息。
  - 可复用：主动消息信号和 `ChatWindow._on_proactive_message()`。
  - 需注意：被动互动气泡应与主对话框视觉状态分离，不应创建第二套 Agent 流程。
- **实现5**: `tests/test_chat_tts_flow.py`
  - 模式：通过 monkeypatch 替换 `LLMManager`、`AgentManager`、`SpriteManager`，直接实例化 `ChatWindow` 验证状态机。
  - 可复用：离线测试 ChatWindow UI 行为、TTS 队列和发送入口。
  - 需注意：STT 和音频设备测试应避免依赖真实麦克风或真实服务。

### 2. 项目约定

- **命名约定**: 配置类使用 `PascalCase`，Qt 私有控件和方法使用 `_snake_case`，测试函数使用 `test_...`。
- **文件组织**: 配置在 `config/`，设置页在 `ui/settings/pages/`，聊天交互在 `ui/chat/`，新增 STT 能力应放入独立 `stt/` 包。
- **导入顺序**: 标准库、第三方库、项目内部模块分组；现有文件未强制排序工具，计划沿用局部风格。
- **代码风格**: 4 空格缩进，PySide6 页面使用模块级 QSS 字符串，pytest 直接断言行为。

### 3. 可复用组件清单

- `config.manager.ConfigManager`: 配置加载与分文件保存。
- `config.schema.ASRConfig`: ASR / STT 配置入口，需扩展而不是新增并行配置。
- `config.schema.SystemConfig`: 字体、字号与显示行为配置入口。
- `ui.widgets.rose_spin_box.RoseSpinBox`: 设置页数字控件。
- `ui.theme.SAKURA_COMBO_BOX_STYLE`: 设置中心下拉框统一样式。
- `ui.chat.window.ChatWindow._on_send`: 文本发送主入口。
- `ui.chat.window.ChatWindow._begin_new_tts_turn`: 用户新输入时中断旧 TTS 轮次。
- `agent.proactive.ProactiveScheduler.proactive_message`: 主动消息事件来源。

### 4. 测试策略

- **测试框架**: pytest。
- **测试模式**: 配置模型单元测试、设置页 apply/reset 测试、ChatWindow 离线实例化测试、STT 适配器 mock 测试。
- **参考文件**: `tests/test_config.py`、`tests/test_settings_window.py`、`tests/test_chat_window_scale.py`、`tests/test_chat_tts_flow.py`、`tests/test_tts_pipeline.py`。
- **覆盖要求**: 字体和字号配置持久化、系统页实时保存、被动气泡显示与隐藏、STT 成功文本进入发送入口、STT 失败反馈、STT 开始时中断 TTS。

### 5. 依赖和集成点

- **外部依赖**: 现有 `PySide6`、`openai` 可支撑麦克风录音 UI 和 OpenAI Whisper 转写；若执行计划选择本地 Vosk / faster-whisper，需要在实施前单独评估依赖体积。
- **内部依赖**: `SettingsWindow._launch_chat()` 负责把配置传入 `ChatWindow`；`APIPage` 负责 ASR 配置编辑；`SystemPage` 负责显示和被动互动配置。
- **集成方式**: STT worker 通过 Qt `Signal` 回主线程，成功后填充输入框并调用同一发送方法；被动互动复用主动消息信号，只改变展示形态。
- **配置来源**: `data/config/api.yaml` 中的 `asr`，`data/config/system_config.yaml` 中的显示与被动互动配置。

### 6. 技术选型理由

- **为什么用这个方案**: Phase 5 的三类能力都已在现有配置和聊天窗中有入口，沿用现有架构可以最小化跨模块冲击。
- **优势**: 不新增 Agent 主链路，不绕过 `SessionContext`，测试可继续离线运行。
- **劣势和风险**: STT 真实麦克风和真实转写服务仍需要人工环境联调；计划中必须把设备和网络依赖隔离为可 mock 的适配器。

### 7. 关键风险点

- **并发问题**: STT 录音、LLM worker、TTS worker 可能同时运行，必须用明确状态和按钮禁用避免重复启动。
- **边界条件**: 空转写、转写失败、用户在 STT 期间手动发送、旧 STT 结果晚到。
- **性能瓶颈**: 录音缓冲和转写请求不能阻塞 Qt 主线程。
- **安全考虑**: 本计划不新增安全验收项；API key 和本地音频路径继续按项目既有敏感配置规则处理。
