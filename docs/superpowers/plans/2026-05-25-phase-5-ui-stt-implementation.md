# Phase 5 桌宠体验、UI 与 STT Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 完成 Phase 5 的桌宠显示配置、被动互动气泡、STT 语音输入与 STT / TTS 状态协调。

**Architecture:** 复用现有配置分层：`SystemConfig` 承载显示与被动互动运行参数，`APIConfig.asr` 承载 STT 服务参数。`ChatWindow` 继续作为输入输出状态机，STT 结果必须回到 `_on_send()` 文本主入口，避免绕过 Agent、SessionContext、日志和 TTS 管线。

**Tech Stack:** Python、PySide6、pytest、Pydantic、OpenAI Python SDK、现有 Yumetsuki Agent / TTS / 配置系统。

---

## Scope Check

Phase 5 spec 涵盖三个紧密相关的交互子系统：显示配置、被动互动气泡、STT。它们都依赖 `ChatWindow` 的显示状态、输入状态和 TTS 中断语义，因此本计划保持为一个顺序执行的总计划。执行时每个任务都必须独立通过测试，任务之间按配置层 → UI 层 → STT 适配层 → 聊天窗集成推进。

## File Structure

- Modify: `config/schema.py`
  - 扩展 `ASRConfig`、新增 `ChatDisplayConfig` 与 `PassiveInteractionConfig`，挂到 `SystemConfig`。
- Modify: `config/manager.py`
  - 保持现有加载保存接口；只在测试中确认新增字段自动持久化。
- Modify: `ui/settings/pages/system_page.py`
  - 增加字体、字号、聊天缩放、气泡宽度、被动互动开关与停留时长控件。
- Modify: `ui/settings/pages/api_page.py`
  - 扩展 ASR 设置：引擎、Base URL、API Key、模型、语言、录音超时、静音阈值。
- Modify: `ui/settings/window.py`
  - 启动聊天窗时传入 `system_config` 和 `asr_config`。
- Modify: `ui/chat/window.py`
  - 接入显示配置、被动气泡、STT 按钮状态、STT worker、TTS 中断。
- Create: `stt/__init__.py`
  - 导出 STT 公共入口。
- Create: `stt/types.py`
  - 定义转写结果模型。
- Create: `stt/adapter.py`
  - 定义 STT 适配器抽象。
- Create: `stt/adapters/__init__.py`
  - 导出具体适配器。
- Create: `stt/adapters/openai_whisper.py`
  - 使用 OpenAI SDK 的 `audio.transcriptions.create()` 进行转写。
- Create: `stt/manager.py`
  - 根据 `ASRConfig` 创建适配器并提供统一 `transcribe_wav()`。
- Create: `ui/chat/stt_recorder.py`
  - 使用 Qt 音频输入录制 WAV 字节，并提供可测试的静音检测。
- Modify: `docs/architecture.md`
  - 补充 STT 模块与 Phase 5 聊天主流程。
- Modify: `docs/development.md`
  - 补充 Phase 5 测试入口和真实设备联调边界。
- Modify: `docs/ui-guidelines.md`
  - 补充被动互动气泡和 STT 按钮状态规范。
- Modify: `docs/README.md`
  - 更新 Phase 5 进度入口。
- Test: `tests/test_config.py`
  - 覆盖新增配置持久化。
- Test: `tests/test_settings_window.py`
  - 覆盖 API / 系统设置页新增控件 apply/reset。
- Test: `tests/test_chat_window_scale.py`
  - 覆盖显示配置影响聊天窗字体与缩放。
- Test: `tests/test_chat_passive_bubble.py`
  - 覆盖被动气泡显示、隐藏、与主对话框互斥。
- Test: `tests/test_stt_adapter.py`
  - 覆盖 STT 适配器与 manager。
- Test: `tests/test_stt_recorder.py`
  - 覆盖录音参数和静音检测。
- Test: `tests/test_chat_stt_flow.py`
  - 覆盖 STT 成功、失败、旧结果失效、TTS 中断。

---

### Task 1: 配置模型与设置页字段

**Files:**
- Modify: `config/schema.py`
- Modify: `ui/settings/pages/api_page.py`
- Modify: `ui/settings/pages/system_page.py`
- Test: `tests/test_config.py`
- Test: `tests/test_settings_window.py`

- [ ] **Step 1: Write failing config tests**

Add to `tests/test_config.py`:

```python
def test_system_config_exposes_phase5_display_and_passive_settings():
    cfg = SystemConfig()

    assert cfg.chat_display.font_scale == 1.0
    assert cfg.chat_display.bubble_scale == 1.0
    assert cfg.passive_interaction.enabled is False
    assert cfg.passive_interaction.bubble_max_width == 280
    assert cfg.passive_interaction.bubble_duration_seconds == 8


def test_save_and_reload_phase5_system_config(tmp_path):
    mgr = ConfigManager(config_dir=tmp_path)
    mgr.system.chat_display.font_scale = 1.25
    mgr.system.chat_display.bubble_scale = 0.9
    mgr.system.passive_interaction.enabled = True
    mgr.system.passive_interaction.bubble_max_width = 320
    mgr.system.passive_interaction.bubble_duration_seconds = 12
    mgr.save_system()

    loaded = ConfigManager(config_dir=tmp_path).system

    assert loaded.chat_display.font_scale == 1.25
    assert loaded.chat_display.bubble_scale == 0.9
    assert loaded.passive_interaction.enabled is True
    assert loaded.passive_interaction.bubble_max_width == 320
    assert loaded.passive_interaction.bubble_duration_seconds == 12


def test_asr_config_exposes_phase5_runtime_settings():
    mgr = ConfigManager()
    cfg = mgr.api.asr

    assert cfg.engine == "none"
    assert cfg.base_url == ""
    assert cfg.api_key == ""
    assert cfg.model == "whisper-1"
    assert cfg.language == "zh"
    assert cfg.record_timeout_seconds == 20
    assert cfg.silence_threshold == 0.02
    assert cfg.silence_duration_ms == 1200
```

- [ ] **Step 2: Run config tests and verify failure**

Run:

```bash
python -m pytest tests/test_config.py::test_system_config_exposes_phase5_display_and_passive_settings tests/test_config.py::test_save_and_reload_phase5_system_config tests/test_config.py::test_asr_config_exposes_phase5_runtime_settings -q
```

Expected: FAIL because `chat_display`、`passive_interaction` and new ASR fields do not exist.

- [ ] **Step 3: Extend config models**

Modify `config/schema.py`:

```python
class ASRConfig(BaseModel):
    engine: str = "none"
    model_path: str = ""
    base_url: str = ""
    api_key: str = ""
    model: str = "whisper-1"
    language: str = "zh"
    record_timeout_seconds: int = 20
    silence_threshold: float = 0.02
    silence_duration_ms: int = 1200


class ChatDisplayConfig(BaseModel):
    font_scale: float = 1.0
    bubble_scale: float = 1.0


class PassiveInteractionConfig(BaseModel):
    enabled: bool = False
    bubble_max_width: int = 280
    bubble_duration_seconds: int = 8
```

Then update `SystemConfig`:

```python
class SystemConfig(BaseModel):
    language: str = "zh-CN"
    theme: str = "dark"
    font_family: str = "Microsoft YaHei"
    font_size: int = 14
    proxy: str = ""
    chat_display: ChatDisplayConfig = Field(default_factory=ChatDisplayConfig)
    passive_interaction: PassiveInteractionConfig = Field(default_factory=PassiveInteractionConfig)
    logging: "LoggingConfig" = Field(default_factory=lambda: LoggingConfig())
```

- [ ] **Step 4: Write failing settings page tests**

Add to `tests/test_settings_window.py`:

```python
def test_api_page_asr_phase5_fields_apply_and_reset():
    _app()
    config = APIConfig()
    page = APIPage(config)

    page._asr_engine.setCurrentText("openai_whisper")
    page._asr_base_url.setText("https://api.openai.com/v1")
    page._asr_api_key.setText("sk-local-test")
    page._asr_model.setText("whisper-1")
    page._asr_language.setCurrentText("ja")
    page._asr_record_timeout.setValue(25)
    page._asr_silence_threshold.setValue(5)
    page._asr_silence_duration.setValue(1500)
    page.apply()

    assert config.asr.engine == "openai_whisper"
    assert config.asr.base_url == "https://api.openai.com/v1"
    assert config.asr.api_key == "sk-local-test"
    assert config.asr.model == "whisper-1"
    assert config.asr.language == "ja"
    assert config.asr.record_timeout_seconds == 25
    assert config.asr.silence_threshold == 0.05
    assert config.asr.silence_duration_ms == 1500

    config.asr.engine = "none"
    config.asr.base_url = ""
    config.asr.api_key = ""
    config.asr.model = "whisper-1"
    config.asr.language = "zh"
    config.asr.record_timeout_seconds = 20
    config.asr.silence_threshold = 0.02
    config.asr.silence_duration_ms = 1200
    page.reset()

    assert page._asr_engine.currentText() == "none"
    assert page._asr_base_url.text() == ""
    assert page._asr_api_key.text() == ""
    assert page._asr_language.currentText() == "zh"
    assert page._asr_record_timeout.value() == 20
    assert page._asr_silence_threshold.value() == 2
    assert page._asr_silence_duration.value() == 1200
```

Add a system page test:

```python
def test_system_page_phase5_display_fields_apply():
    from config.schema import SystemConfig
    from ui.settings.pages.system_page import SystemPage

    _app()
    config = SystemConfig()
    page = SystemPage(config)

    page._chat_font_scale.setValue(125)
    page._bubble_scale.setValue(90)
    page._passive_enabled.setCurrentText("启用")
    page._bubble_max_width.setValue(320)
    page._bubble_duration.setValue(12)
    page.apply()

    assert config.chat_display.font_scale == 1.25
    assert config.chat_display.bubble_scale == 0.9
    assert config.passive_interaction.enabled is True
    assert config.passive_interaction.bubble_max_width == 320
    assert config.passive_interaction.bubble_duration_seconds == 12
```

- [ ] **Step 5: Run settings tests and verify failure**

Run:

```bash
python -m pytest tests/test_settings_window.py::test_api_page_asr_phase5_fields_apply_and_reset tests/test_settings_window.py::test_system_page_phase5_display_fields_apply -q
```

Expected: FAIL because the new controls do not exist.

- [ ] **Step 6: Implement APIPage ASR controls**

Modify `ui/settings/pages/api_page.py` ASR group:

```python
self._asr_engine = QComboBox()
self._asr_engine.addItems(["none", "openai_whisper"])
self._asr_engine.setCurrentText(config.asr.engine)
asr_form.addRow("引擎:", self._asr_engine)

self._asr_base_url = QLineEdit(config.asr.base_url)
self._asr_base_url.setPlaceholderText("OpenAI API Base URL，留空使用官方默认")
asr_form.addRow("Base URL:", self._asr_base_url)

self._asr_api_key = QLineEdit(config.asr.api_key)
self._asr_api_key.setEchoMode(QLineEdit.EchoMode.Password)
asr_form.addRow("API Key:", self._asr_api_key)

self._asr_model = QLineEdit(config.asr.model)
self._asr_model.setPlaceholderText("whisper-1")
asr_form.addRow("模型:", self._asr_model)

self._asr_language = QComboBox()
self._asr_language.setEditable(True)
self._asr_language.addItems(["zh", "ja", "en", "ko", "yue"])
self._asr_language.setCurrentText(config.asr.language)
self._asr_language.setMaximumWidth(220)
asr_form.addRow("语言:", self._asr_language)

self._asr_record_timeout = RoseSpinBox()
self._asr_record_timeout.setRange(3, 120)
self._asr_record_timeout.setValue(config.asr.record_timeout_seconds)
self._asr_record_timeout.setSuffix(" 秒")
asr_form.addRow("录音超时:", self._asr_record_timeout)

self._asr_silence_threshold = RoseSpinBox()
self._asr_silence_threshold.setRange(1, 50)
self._asr_silence_threshold.setValue(int(config.asr.silence_threshold * 100))
self._asr_silence_threshold.setSuffix("%")
asr_form.addRow("静音阈值:", self._asr_silence_threshold)

self._asr_silence_duration = RoseSpinBox()
self._asr_silence_duration.setRange(300, 5000)
self._asr_silence_duration.setValue(config.asr.silence_duration_ms)
self._asr_silence_duration.setSuffix(" ms")
asr_form.addRow("静音结束:", self._asr_silence_duration)
```

Update `apply()`:

```python
self._config.asr.engine = self._asr_engine.currentText()
self._config.asr.base_url = self._asr_base_url.text()
self._config.asr.api_key = self._asr_api_key.text()
self._config.asr.model = self._asr_model.text()
self._config.asr.language = self._asr_language.currentText()
self._config.asr.record_timeout_seconds = self._asr_record_timeout.value()
self._config.asr.silence_threshold = self._asr_silence_threshold.value() / 100.0
self._config.asr.silence_duration_ms = self._asr_silence_duration.value()
```

Update `reset()`:

```python
self._asr_engine.setCurrentText(self._config.asr.engine)
self._asr_base_url.setText(self._config.asr.base_url)
self._asr_api_key.setText(self._config.asr.api_key)
self._asr_model.setText(self._config.asr.model)
self._asr_language.setCurrentText(self._config.asr.language)
self._asr_record_timeout.setValue(self._config.asr.record_timeout_seconds)
self._asr_silence_threshold.setValue(int(self._config.asr.silence_threshold * 100))
self._asr_silence_duration.setValue(self._config.asr.silence_duration_ms)
```

- [ ] **Step 7: Implement SystemPage display controls**

Modify imports in `ui/settings/pages/system_page.py`:

```python
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QLineEdit,
    QComboBox, QLabel, QGroupBox,
)
```

Add controls under the appearance group after `_font_size`:

```python
self._chat_font_scale = RoseSpinBox()
self._chat_font_scale.setRange(75, 150)
self._chat_font_scale.setValue(int(config.chat_display.font_scale * 100))
self._chat_font_scale.setSuffix("%")
self._chat_font_scale.setMinimumWidth(280)
self._chat_font_scale.valueChanged.connect(self._save_live)
app_form.addRow("聊天字号倍率:", self._chat_font_scale)

self._bubble_scale = RoseSpinBox()
self._bubble_scale.setRange(75, 150)
self._bubble_scale.setValue(int(config.chat_display.bubble_scale * 100))
self._bubble_scale.setSuffix("%")
self._bubble_scale.setMinimumWidth(280)
self._bubble_scale.valueChanged.connect(self._save_live)
app_form.addRow("气泡缩放:", self._bubble_scale)
```

Add a new passive group:

```python
passive = QGroupBox("被动互动")
passive_form = QFormLayout(passive)
passive_form.setSpacing(10)

self._passive_enabled = QComboBox()
self._passive_enabled.addItems(["关闭", "启用"])
self._passive_enabled.setCurrentText("启用" if config.passive_interaction.enabled else "关闭")
self._passive_enabled.currentTextChanged.connect(self._save_live)
passive_form.addRow("气泡模式:", self._passive_enabled)

self._bubble_max_width = RoseSpinBox()
self._bubble_max_width.setRange(180, 520)
self._bubble_max_width.setValue(config.passive_interaction.bubble_max_width)
self._bubble_max_width.setSuffix(" px")
self._bubble_max_width.valueChanged.connect(self._save_live)
passive_form.addRow("气泡最大宽度:", self._bubble_max_width)

self._bubble_duration = RoseSpinBox()
self._bubble_duration.setRange(3, 60)
self._bubble_duration.setValue(config.passive_interaction.bubble_duration_seconds)
self._bubble_duration.setSuffix(" 秒")
self._bubble_duration.valueChanged.connect(self._save_live)
passive_form.addRow("停留时长:", self._bubble_duration)

layout.addWidget(passive)
```

Update `apply()`:

```python
self._config.chat_display.font_scale = self._chat_font_scale.value() / 100.0
self._config.chat_display.bubble_scale = self._bubble_scale.value() / 100.0
self._config.passive_interaction.enabled = self._passive_enabled.currentText() == "启用"
self._config.passive_interaction.bubble_max_width = self._bubble_max_width.value()
self._config.passive_interaction.bubble_duration_seconds = self._bubble_duration.value()
```

- [ ] **Step 8: Run Task 1 tests**

Run:

```bash
python -m pytest tests/test_config.py tests/test_settings_window.py -q
```

Expected: PASS.

- [ ] **Step 9: Commit Task 1**

```bash
git add config/schema.py ui/settings/pages/api_page.py ui/settings/pages/system_page.py tests/test_config.py tests/test_settings_window.py
git commit -m "feat: add phase5 display and stt settings"
```

---

### Task 2: 聊天窗显示配置接入

**Files:**
- Modify: `ui/settings/window.py`
- Modify: `ui/chat/window.py`
- Test: `tests/test_chat_window_scale.py`
- Test: `tests/test_chat_tts_flow.py`

- [ ] **Step 1: Write failing ChatWindow display tests**

Add to `tests/test_chat_window_scale.py`:

```python
from config.schema import LLMConfig, SystemConfig
from ui.chat.window import ChatWindow


def test_chat_window_uses_system_font_scale(monkeypatch):
    from tests.test_chat_tts_flow import _FakeAgentManager, _FakeLLMManager, _FakeSpriteManager, _app

    _app()
    monkeypatch.setattr("ui.chat.window.LLMManager", _FakeLLMManager)
    monkeypatch.setattr("ui.chat.window.AgentManager", _FakeAgentManager)
    monkeypatch.setattr("ui.chat.window.SpriteManager", _FakeSpriteManager)

    system_config = SystemConfig()
    system_config.font_family = "Microsoft YaHei"
    system_config.font_size = 16
    system_config.chat_display.font_scale = 1.25

    window = ChatWindow(LLMConfig(), system_config=system_config)
    window._set_dialog_text("测试文字")

    assert "font-size: 20px" in window._dialog_box.text()
    assert "Microsoft YaHei" in window._dialog_box.styleSheet()
    window.close()


def test_launch_chat_passes_system_config(monkeypatch):
    from tests.test_chat_tts_flow import _app
    from ui.settings.window import SettingsWindow

    _app()
    captured = {}

    class DummyChatWindow:
        def __init__(self, llm_config, **kwargs):
            captured["system_config"] = kwargs.get("system_config")
            self._tts_session_id = "session-display"

        def show(self):
            return None

        def set_memory_store(self, memory_store):
            return None

    monkeypatch.setattr("ui.settings.window.ChatWindow", DummyChatWindow)
    monkeypatch.setattr("ui.settings.window.PluginHost", lambda *_: type("P", (), {"load": lambda self: None})())
    monkeypatch.setattr("ui.settings.window.MCPHost", lambda *_: type("M", (), {"connect_all": lambda self: None})())
    monkeypatch.setattr("ui.settings.window.ToolRegistry", lambda **_: type("T", (), {})())

    class DummyLoader:
        def __init__(self, *_args, **_kwargs):
            self.memory_ready = type("S", (), {"connect": lambda self, *_: None})()
            self.memory_failed = type("S", (), {"connect": lambda self, *_: None})()

        def start(self):
            return None

    monkeypatch.setattr("ui.settings.window.MemoryLoaderThread", DummyLoader)

    window = SettingsWindow()
    window._launch_chat()

    assert captured["system_config"] == window._config.system
```

- [ ] **Step 2: Run display tests and verify failure**

Run:

```bash
python -m pytest tests/test_chat_window_scale.py::test_chat_window_uses_system_font_scale tests/test_chat_window_scale.py::test_launch_chat_passes_system_config -q
```

Expected: FAIL because `ChatWindow.__init__()` does not accept `system_config`.

- [ ] **Step 3: Pass system config from SettingsWindow**

Modify `ui/settings/window.py` in `_launch_chat()`:

```python
self._chat_window = ChatWindow(
    self._config.api.llm,
    character_dir=char_dir,
    tool_registry=tool_registry,
    memory_store=None,
    user_id=self._config.memory.user_id,
    settings_window_factory=lambda: self,
    agent_config=self._config.agent,
    tts_config=self._config.api.tts,
    system_config=self._config.system,
    asr_config=self._config.api.asr,
    log_service=self._log_service,
)
```

- [ ] **Step 4: Apply display config in ChatWindow**

Modify imports in `ui/chat/window.py`:

```python
from config.schema import AgentConfig, ASRConfig, LLMConfig, SystemConfig, TTSConfig
```

Extend `ChatWindow.__init__()` signature:

```python
def __init__(
    self,
    config: LLMConfig,
    character_dir: Path | None = None,
    tool_registry: ToolRegistry | None = None,
    memory_store=None,
    user_id: str | None = None,
    settings_window_factory=None,
    agent_config=None,
    tts_config: TTSConfig | None = None,
    system_config: SystemConfig | None = None,
    asr_config: ASRConfig | None = None,
    log_service=None,
):
```

Add after `super().__init__()`:

```python
self._system_config = system_config or SystemConfig()
self._asr_config = asr_config or ASRConfig()
self._display_font_family = self._system_config.font_family or "Microsoft YaHei"
self._display_font_size = max(10, int(self._system_config.font_size))
self._display_font_scale = max(0.75, min(1.5, self._system_config.chat_display.font_scale))
self._bubble_scale = max(0.75, min(1.5, self._system_config.chat_display.bubble_scale))
```

Update `_set_dialog_text()`:

```python
font = int(self._display_font_size * self._display_font_scale * self._scale)
```

Update `_rebuild_stylesheet()` font variables:

```python
font = int(self._display_font_size * self._display_font_scale * s)
name_font = int(self.BASE_NAME_FONT * self._display_font_scale * s)
input_font = int(self.BASE_INPUT_FONT * self._display_font_scale * s)
```

Update dialog and input styles to include font family:

```python
font-family: "{self._display_font_family}";
```

- [ ] **Step 5: Run display tests**

Run:

```bash
python -m pytest tests/test_chat_window_scale.py tests/test_chat_tts_flow.py::test_launch_chat_passes_tts_config -q
```

Expected: PASS.

- [ ] **Step 6: Commit Task 2**

```bash
git add ui/settings/window.py ui/chat/window.py tests/test_chat_window_scale.py
git commit -m "feat: apply chat display settings"
```

---

### Task 3: 被动互动气泡

**Files:**
- Modify: `ui/chat/window.py`
- Test: `tests/test_chat_passive_bubble.py`

- [ ] **Step 1: Write failing passive bubble tests**

Create `tests/test_chat_passive_bubble.py`:

```python
from config.schema import LLMConfig, SystemConfig
from ui.chat.window import ChatWindow
from tests.test_chat_tts_flow import _FakeAgentManager, _FakeLLMManager, _FakeSpriteManager, _app


def _window(monkeypatch, enabled=True):
    _app()
    monkeypatch.setattr("ui.chat.window.LLMManager", _FakeLLMManager)
    monkeypatch.setattr("ui.chat.window.AgentManager", _FakeAgentManager)
    monkeypatch.setattr("ui.chat.window.SpriteManager", _FakeSpriteManager)
    cfg = SystemConfig()
    cfg.passive_interaction.enabled = enabled
    cfg.passive_interaction.bubble_max_width = 300
    cfg.passive_interaction.bubble_duration_seconds = 4
    return ChatWindow(LLMConfig(), system_config=cfg)


def test_passive_message_uses_bubble_when_enabled(monkeypatch):
    window = _window(monkeypatch, enabled=True)

    window._on_proactive_message("休息一下吧。", "idle_chat")

    assert window._passive_bubble.isVisible()
    assert "休息一下吧。" in window._passive_bubble.text()
    assert not window._panel.isVisible()
    window.close()


def test_passive_message_uses_dialog_when_disabled(monkeypatch):
    window = _window(monkeypatch, enabled=False)

    window._on_proactive_message("休息一下吧。", "idle_chat")

    assert not window._passive_bubble.isVisible()
    assert window._panel.isVisible()
    assert "休息一下吧。" in window._dialog_box.text()
    window.close()


def test_user_send_restores_main_panel(monkeypatch):
    window = _window(monkeypatch, enabled=True)
    calls = []
    monkeypatch.setattr(window, "_begin_new_tts_turn", lambda: None)
    monkeypatch.setattr(
        "ui.chat.window.LLMWorker",
        lambda chat_engine, user_input: type(
            "W",
            (),
            {
                "chunk_received": type("S", (), {"connect": lambda self, *_: None})(),
                "finished_signal": type("S", (), {"connect": lambda self, *_: None})(),
                "error_signal": type("S", (), {"connect": lambda self, *_: None})(),
                "start": lambda self: calls.append(user_input),
            },
        )(),
    )

    window._on_proactive_message("休息一下吧。", "idle_chat")
    window._input.setText("好")
    window._on_send()

    assert not window._passive_bubble.isVisible()
    assert window._panel.isVisible()
    assert calls == ["好"]
    window.close()
```

- [ ] **Step 2: Run passive tests and verify failure**

Run:

```bash
python -m pytest tests/test_chat_passive_bubble.py -q
```

Expected: FAIL because `_passive_bubble` does not exist.

- [ ] **Step 3: Add passive bubble widget to ChatWindow**

Modify `ui/chat/window.py` imports:

```python
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QLabel, QPushButton, QMenu,
    QApplication, QSizePolicy, QScrollArea,
)
```

Add in `_setup_ui()` after `_panel` setup:

```python
self._passive_bubble = QLabel(self)
self._passive_bubble.setWordWrap(True)
self._passive_bubble.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
self._passive_bubble.hide()
self._passive_bubble_timer = QTimer(self)
self._passive_bubble_timer.setSingleShot(True)
self._passive_bubble_timer.timeout.connect(self._hide_passive_bubble)
```

Add methods:

```python
def _show_passive_bubble(self, text: str) -> None:
    self._panel.hide()
    self._passive_bubble.setText(escape(text))
    self._passive_bubble.setVisible(True)
    self._position_passive_bubble()
    duration_ms = max(1000, self._system_config.passive_interaction.bubble_duration_seconds * 1000)
    self._passive_bubble_timer.start(duration_ms)

def _hide_passive_bubble(self) -> None:
    self._passive_bubble_timer.stop()
    self._passive_bubble.hide()
    self._panel.show()

def _position_passive_bubble(self) -> None:
    width = int(self._system_config.passive_interaction.bubble_max_width * self._bubble_scale * self._scale)
    width = max(160, min(width, self.width() - 24))
    self._passive_bubble.setFixedWidth(width)
    self._passive_bubble.adjustSize()
    height = max(42, self._passive_bubble.height() + int(12 * self._scale))
    x = max(8, int((self.width() - width) / 2))
    y = max(8, int(self.height() * 0.58 - height))
    self._passive_bubble.setGeometry(x, y, width, height)
```

Update `_rebuild_stylesheet()`:

```python
self._passive_bubble.setStyleSheet(f"""
    QLabel {{
        background: rgba(255, 250, 252, 0.88);
        border: {control_border}px solid #d4567a;
        border-radius: {max(10, int(14 * s))}px;
        color: #4a3040;
        font-family: "{self._display_font_family}";
        font-size: {font}px;
        padding: {max(8, int(10 * s))}px {max(10, int(14 * s))}px;
    }}
""")
```

Update `_apply_scale()`:

```python
if hasattr(self, "_passive_bubble") and self._passive_bubble.isVisible():
    self._position_passive_bubble()
```

- [ ] **Step 4: Wire proactive message to passive display**

Modify `_on_proactive_message()`:

```python
def _on_proactive_message(self, message: str, source: str):
    """收到主动消息：被动模式用气泡展示，否则以角色身份显示。"""
    if self._system_config.passive_interaction.enabled:
        self._show_passive_bubble(message)
        return
    if self._char_name:
        self._set_speaker_name(self._char_name)
    self._set_dialog_text(message)
```

Modify `_on_send()` near the start:

```python
self._hide_passive_bubble()
```

- [ ] **Step 5: Run passive tests**

Run:

```bash
python -m pytest tests/test_chat_passive_bubble.py tests/test_chat_window_scale.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit Task 3**

```bash
git add ui/chat/window.py tests/test_chat_passive_bubble.py
git commit -m "feat: add passive interaction bubble"
```

---

### Task 4: STT 适配器与 Manager

**Files:**
- Create: `stt/__init__.py`
- Create: `stt/types.py`
- Create: `stt/adapter.py`
- Create: `stt/adapters/__init__.py`
- Create: `stt/adapters/openai_whisper.py`
- Create: `stt/manager.py`
- Test: `tests/test_stt_adapter.py`

- [ ] **Step 1: Write failing STT adapter tests**

Create `tests/test_stt_adapter.py`:

```python
from types import SimpleNamespace

from config.schema import ASRConfig
from stt.manager import STTManager
from stt.types import STTResult


def test_stt_manager_disabled_returns_empty_result():
    manager = STTManager(ASRConfig(engine="none"))

    result = manager.transcribe_wav(b"RIFF....WAVE")

    assert result == STTResult(text="", language="", confidence=0.0)


def test_stt_manager_rejects_unknown_engine():
    manager = STTManager(ASRConfig(engine="missing"))

    result = manager.transcribe_wav(b"RIFF....WAVE")

    assert result.text == ""
    assert result.error == "不支持的 STT 引擎：missing"


def test_openai_whisper_adapter_sends_audio(monkeypatch):
    captured = {}

    class _Transcriptions:
        def create(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(text="你好呀")

    class _Audio:
        transcriptions = _Transcriptions()

    class _Client:
        audio = _Audio()

    monkeypatch.setattr("stt.adapters.openai_whisper.OpenAI", lambda **kwargs: _Client())

    config = ASRConfig(
        engine="openai_whisper",
        api_key="sk-test",
        base_url="https://api.openai.com/v1",
        model="whisper-1",
        language="zh",
    )
    result = STTManager(config).transcribe_wav(b"RIFF....WAVE")

    assert result.text == "你好呀"
    assert captured["model"] == "whisper-1"
    assert captured["language"] == "zh"
    assert captured["file"][0] == "speech.wav"
```

- [ ] **Step 2: Run STT adapter tests and verify failure**

Run:

```bash
python -m pytest tests/test_stt_adapter.py -q
```

Expected: FAIL because `stt` package does not exist.

- [ ] **Step 3: Create STT types and abstract adapter**

Create `stt/types.py`:

```python
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class STTResult:
    text: str
    language: str = ""
    confidence: float = 0.0
    error: str = ""
```

Create `stt/adapter.py`:

```python
from __future__ import annotations

from abc import ABC, abstractmethod

from stt.types import STTResult


class STTAdapter(ABC):
    @abstractmethod
    def transcribe_wav(self, audio: bytes) -> STTResult:
        raise NotImplementedError
```

Create `stt/__init__.py`:

```python
from stt.manager import STTManager
from stt.types import STTResult

__all__ = ["STTManager", "STTResult"]
```

- [ ] **Step 4: Create OpenAI Whisper adapter**

Create `stt/adapters/__init__.py`:

```python
from stt.adapters.openai_whisper import OpenAIWhisperAdapter

__all__ = ["OpenAIWhisperAdapter"]
```

Create `stt/adapters/openai_whisper.py`:

```python
from __future__ import annotations

from io import BytesIO

from openai import OpenAI

from config.schema import ASRConfig
from stt.adapter import STTAdapter
from stt.types import STTResult


class OpenAIWhisperAdapter(STTAdapter):
    def __init__(self, config: ASRConfig):
        client_kwargs = {}
        if config.api_key:
            client_kwargs["api_key"] = config.api_key
        if config.base_url:
            client_kwargs["base_url"] = config.base_url
        self._client = OpenAI(**client_kwargs)
        self._model = config.model or "whisper-1"
        self._language = config.language or "zh"

    def transcribe_wav(self, audio: bytes) -> STTResult:
        if not audio:
            return STTResult(text="", language=self._language, error="录音内容为空")
        wav_file = BytesIO(audio)
        wav_file.name = "speech.wav"
        try:
            response = self._client.audio.transcriptions.create(
                model=self._model,
                file=("speech.wav", wav_file, "audio/wav"),
                language=self._language,
            )
        except Exception as exc:
            return STTResult(text="", language=self._language, error=str(exc))
        return STTResult(text=(getattr(response, "text", "") or "").strip(), language=self._language)
```

- [ ] **Step 5: Create STTManager**

Create `stt/manager.py`:

```python
from __future__ import annotations

from config.schema import ASRConfig
from stt.adapters.openai_whisper import OpenAIWhisperAdapter
from stt.types import STTResult


class STTManager:
    def __init__(self, config: ASRConfig):
        self._config = config
        self._adapter = self._create_adapter(config)

    @staticmethod
    def _create_adapter(config: ASRConfig):
        engine = (config.engine or "none").strip().lower()
        if engine == "none":
            return None
        if engine == "openai_whisper":
            return OpenAIWhisperAdapter(config)
        return engine

    def transcribe_wav(self, audio: bytes) -> STTResult:
        if self._adapter is None:
            return STTResult(text="")
        if isinstance(self._adapter, str):
            return STTResult(text="", error=f"不支持的 STT 引擎：{self._adapter}")
        return self._adapter.transcribe_wav(audio)
```

- [ ] **Step 6: Run STT adapter tests**

Run:

```bash
python -m pytest tests/test_stt_adapter.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit Task 4**

```bash
git add stt tests/test_stt_adapter.py
git commit -m "feat: add stt adapter layer"
```

---

### Task 5: STT 录音控制器

**Files:**
- Create: `ui/chat/stt_recorder.py`
- Test: `tests/test_stt_recorder.py`

- [ ] **Step 1: Write failing recorder tests**

Create `tests/test_stt_recorder.py`:

```python
from ui.chat.stt_recorder import STTRecorder


def test_stt_recorder_detects_silence_from_pcm16_samples():
    recorder = STTRecorder(record_timeout_seconds=20, silence_threshold=0.02, silence_duration_ms=1200)

    assert recorder._is_silent(b"\x00\x00" * 1600) is True
    assert recorder._is_silent((32767).to_bytes(2, "little", signed=True) * 1600) is False


def test_stt_recorder_builds_wav_bytes():
    recorder = STTRecorder(record_timeout_seconds=20, silence_threshold=0.02, silence_duration_ms=1200)

    wav = recorder._build_wav(b"\x00\x00" * 1600)

    assert wav.startswith(b"RIFF")
    assert b"WAVE" in wav[:16]
    assert len(wav) > 44
```

- [ ] **Step 2: Run recorder tests and verify failure**

Run:

```bash
python -m pytest tests/test_stt_recorder.py -q
```

Expected: FAIL because `ui.chat.stt_recorder` does not exist.

- [ ] **Step 3: Implement STTRecorder**

Create `ui/chat/stt_recorder.py`:

```python
from __future__ import annotations

import audioop
import wave
from io import BytesIO

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtMultimedia import QAudioFormat, QAudioSource, QMediaDevices


class STTRecorder(QObject):
    audio_ready = Signal(bytes)
    error = Signal(str)

    SAMPLE_RATE = 16000
    CHANNELS = 1
    SAMPLE_WIDTH = 2

    def __init__(self, record_timeout_seconds: int, silence_threshold: float, silence_duration_ms: int, parent=None):
        super().__init__(parent)
        self._record_timeout_seconds = max(3, record_timeout_seconds)
        self._silence_threshold = max(0.001, silence_threshold)
        self._silence_duration_ms = max(300, silence_duration_ms)
        self._source = None
        self._device = None
        self._buffer = bytearray()
        self._silent_ms = 0
        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(100)
        self._poll_timer.timeout.connect(self._poll_audio)
        self._timeout_timer = QTimer(self)
        self._timeout_timer.setSingleShot(True)
        self._timeout_timer.timeout.connect(self.stop)

    def start(self) -> None:
        if self._source is not None:
            return
        audio_input = QMediaDevices.defaultAudioInput()
        if audio_input.isNull():
            self.error.emit("未找到可用麦克风")
            return
        audio_format = QAudioFormat()
        audio_format.setSampleRate(self.SAMPLE_RATE)
        audio_format.setChannelCount(self.CHANNELS)
        audio_format.setSampleFormat(QAudioFormat.SampleFormat.Int16)
        self._source = QAudioSource(audio_input, audio_format, self)
        self._device = self._source.start()
        if self._device is None:
            self.error.emit("麦克风启动失败")
            self._source = None
            return
        self._buffer.clear()
        self._silent_ms = 0
        self._poll_timer.start()
        self._timeout_timer.start(self._record_timeout_seconds * 1000)

    def stop(self) -> None:
        if self._source is None:
            return
        self._poll_audio()
        self._poll_timer.stop()
        self._timeout_timer.stop()
        self._source.stop()
        self._source.deleteLater()
        self._source = None
        self._device = None
        self.audio_ready.emit(self._build_wav(bytes(self._buffer)))

    def cancel(self) -> None:
        self._poll_timer.stop()
        self._timeout_timer.stop()
        if self._source is not None:
            self._source.stop()
            self._source.deleteLater()
        self._source = None
        self._device = None
        self._buffer.clear()

    def _poll_audio(self) -> None:
        if self._device is None:
            return
        chunk = bytes(self._device.readAll())
        if not chunk:
            return
        self._buffer.extend(chunk)
        if self._is_silent(chunk):
            self._silent_ms += self._poll_timer.interval()
        else:
            self._silent_ms = 0
        if self._silent_ms >= self._silence_duration_ms and len(self._buffer) > self.SAMPLE_RATE:
            self.stop()

    def _is_silent(self, pcm: bytes) -> bool:
        if not pcm:
            return True
        rms = audioop.rms(pcm, self.SAMPLE_WIDTH)
        return (rms / 32768.0) < self._silence_threshold

    def _build_wav(self, pcm: bytes) -> bytes:
        output = BytesIO()
        with wave.open(output, "wb") as wav_file:
            wav_file.setnchannels(self.CHANNELS)
            wav_file.setsampwidth(self.SAMPLE_WIDTH)
            wav_file.setframerate(self.SAMPLE_RATE)
            wav_file.writeframes(pcm)
        return output.getvalue()
```

- [ ] **Step 4: Run recorder tests**

Run:

```bash
python -m pytest tests/test_stt_recorder.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit Task 5**

```bash
git add ui/chat/stt_recorder.py tests/test_stt_recorder.py
git commit -m "feat: add stt recorder"
```

---

### Task 6: ChatWindow STT 主链路集成

**Files:**
- Modify: `ui/chat/window.py`
- Test: `tests/test_chat_stt_flow.py`
- Test: `tests/test_chat_tts_flow.py`

- [ ] **Step 1: Write failing chat STT tests**

Create `tests/test_chat_stt_flow.py`:

```python
from types import SimpleNamespace

from config.schema import ASRConfig, LLMConfig
from stt.types import STTResult
from ui.chat.window import ChatWindow
from tests.test_chat_tts_flow import _FakeAgentManager, _FakeLLMManager, _FakeSpriteManager, _app


def _window(monkeypatch, asr_config=None):
    _app()
    monkeypatch.setattr("ui.chat.window.LLMManager", _FakeLLMManager)
    monkeypatch.setattr("ui.chat.window.AgentManager", _FakeAgentManager)
    monkeypatch.setattr("ui.chat.window.SpriteManager", _FakeSpriteManager)
    monkeypatch.setattr("ui.chat.window.STTManager", lambda config: SimpleNamespace(transcribe_wav=lambda audio: STTResult(text="你好呀")))
    return ChatWindow(LLMConfig(), asr_config=asr_config or ASRConfig(engine="openai_whisper"))


def test_mic_button_disabled_when_stt_engine_is_none(monkeypatch):
    window = _window(monkeypatch, ASRConfig(engine="none"))

    assert window._mic_btn.isEnabled() is False
    assert "未启用" in window._mic_btn.toolTip()
    window.close()


def test_stt_success_text_enters_send_path(monkeypatch):
    window = _window(monkeypatch)
    sent = []
    monkeypatch.setattr(window, "_on_send", lambda: sent.append(window._input.text()))

    window._on_stt_result(STTResult(text="你好呀", language="zh"))

    assert window._input.text() == "你好呀"
    assert sent == ["你好呀"]
    window.close()


def test_stt_empty_result_does_not_send(monkeypatch):
    window = _window(monkeypatch)
    sent = []
    monkeypatch.setattr(window, "_on_send", lambda: sent.append(window._input.text()))

    window._on_stt_result(STTResult(text="", language="zh"))

    assert sent == []
    assert "没有识别到语音" in window._input.placeholderText()
    window.close()


def test_stt_start_interrupts_current_tts(monkeypatch):
    window = _window(monkeypatch)
    calls = []
    monkeypatch.setattr(window, "_begin_new_tts_turn", lambda: calls.append("tts_reset"))
    monkeypatch.setattr(window, "_create_stt_recorder", lambda: SimpleNamespace(
        audio_ready=SimpleNamespace(connect=lambda *_: None),
        error=SimpleNamespace(connect=lambda *_: None),
        start=lambda: calls.append("record_start"),
        cancel=lambda: calls.append("record_cancel"),
    ))

    window._start_stt_recording()

    assert calls == ["tts_reset", "record_start"]
    assert window._is_stt_recording is True
    window.close()
```

- [ ] **Step 2: Run chat STT tests and verify failure**

Run:

```bash
python -m pytest tests/test_chat_stt_flow.py -q
```

Expected: FAIL because `_mic_btn` and STT methods do not exist.

- [ ] **Step 3: Add STT imports and worker**

Modify `ui/chat/window.py` imports:

```python
from stt.manager import STTManager
from stt.types import STTResult
from ui.chat.stt_recorder import STTRecorder
```

Add worker class near `TTSWorker`:

```python
class STTTranscribeWorker(QThread):
    result_ready = Signal(object)

    def __init__(self, manager: STTManager, audio: bytes):
        super().__init__()
        self._manager = manager
        self._audio = audio

    def run(self):
        self.result_ready.emit(self._manager.transcribe_wav(self._audio))
```

- [ ] **Step 4: Wire mic button and STT state**

In `ChatWindow.__init__()` after `_asr_config` assignment:

```python
self._stt_manager = STTManager(self._asr_config)
self._stt_recorder = None
self._stt_worker = None
self._is_stt_recording = False
```

In `_setup_ui()`, replace local `mic_btn` with instance field:

```python
self._mic_btn = QPushButton("🎤")
self._mic_btn.setFixedSize(34, 34)
self._mic_btn.setStyleSheet(self._circle_btn_style())
self._mic_btn.setToolTip("语音输入")
self._mic_btn.clicked.connect(self._toggle_stt_recording)
input_row.addWidget(self._mic_btn)
```

At the end of `_setup_ui()`:

```python
if (self._asr_config.engine or "none") == "none":
    self._mic_btn.setEnabled(False)
    self._mic_btn.setToolTip("语音输入未启用")
```

- [ ] **Step 5: Implement STT methods**

Add methods to `ChatWindow`:

```python
def _toggle_stt_recording(self) -> None:
    if self._is_stt_recording:
        self._stop_stt_recording()
        return
    self._start_stt_recording()

def _create_stt_recorder(self):
    return STTRecorder(
        record_timeout_seconds=self._asr_config.record_timeout_seconds,
        silence_threshold=self._asr_config.silence_threshold,
        silence_duration_ms=self._asr_config.silence_duration_ms,
        parent=self,
    )

def _start_stt_recording(self) -> None:
    if self._worker is not None or self._stt_worker is not None:
        return
    self._hide_passive_bubble()
    self._begin_new_tts_turn()
    self._stt_recorder = self._create_stt_recorder()
    self._stt_recorder.audio_ready.connect(self._on_stt_audio_ready, Qt.ConnectionType.QueuedConnection)
    self._stt_recorder.error.connect(self._on_stt_error, Qt.ConnectionType.QueuedConnection)
    self._is_stt_recording = True
    self._mic_btn.setText("■")
    self._input.setPlaceholderText("正在听...")
    self._stt_recorder.start()

def _stop_stt_recording(self) -> None:
    if self._stt_recorder is None:
        return
    self._stt_recorder.stop()

def _on_stt_audio_ready(self, audio: bytes) -> None:
    self._is_stt_recording = False
    self._mic_btn.setText("🎤")
    self._input.setPlaceholderText("正在识别...")
    self._stt_worker = STTTranscribeWorker(self._stt_manager, audio)
    self._stt_worker.result_ready.connect(self._on_stt_result, Qt.ConnectionType.QueuedConnection)
    self._stt_worker.finished.connect(self._on_stt_worker_finished)
    self._stt_worker.start()

def _on_stt_result(self, result: STTResult) -> None:
    if result.error:
        self._input.setPlaceholderText(f"语音识别失败：{result.error}")
        return
    text = result.text.strip()
    if not text:
        self._input.setPlaceholderText("没有识别到语音")
        return
    self._input.setText(text)
    self._on_send()

def _on_stt_error(self, message: str) -> None:
    self._is_stt_recording = False
    self._mic_btn.setText("🎤")
    self._input.setPlaceholderText(f"语音输入失败：{message}")

def _on_stt_worker_finished(self) -> None:
    if self._stt_worker is not None:
        self._stt_worker.deleteLater()
        self._stt_worker = None
    self._input.setPlaceholderText("输入消息...")
```

Update `closeEvent()`:

```python
if self._stt_recorder is not None:
    self._stt_recorder.cancel()
if self._stt_worker is not None:
    self._stt_worker.wait(100)
```

- [ ] **Step 6: Run chat STT tests**

Run:

```bash
python -m pytest tests/test_chat_stt_flow.py tests/test_chat_tts_flow.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit Task 6**

```bash
git add ui/chat/window.py tests/test_chat_stt_flow.py
git commit -m "feat: connect stt to chat flow"
```

---

### Task 7: 文档同步与全量验证

**Files:**
- Modify: `CLAUDE.md`
- Modify: `docs/README.md`
- Modify: `docs/architecture.md`
- Modify: `docs/development.md`
- Modify: `docs/ui-guidelines.md`

- [ ] **Step 1: Update architecture docs**

Add to `docs/architecture.md` under core module sections:

```markdown
### `stt/`

负责语音输入转文字。

- `stt/types.py`
  语音识别结果模型。
- `stt/adapter.py`
  STT 适配器抽象。
- `stt/adapters/openai_whisper.py`
  OpenAI Whisper 转写适配器。
- `stt/manager.py`
  根据 `ASRConfig` 创建适配器，并向聊天窗提供统一转写入口。
```

Update chat flow:

```markdown
语音输入 → STTRecorder 采集 WAV → STTManager 转写 → ChatWindow 写入输入框 → 复用 `_on_send()` 进入正常聊天主链路
```

- [ ] **Step 2: Update development docs**

Add Phase 5 test commands to `docs/development.md`:

```markdown
- Phase 5 UI / STT：
  - `python -m pytest tests/test_config.py tests/test_settings_window.py tests/test_chat_window_scale.py tests/test_chat_passive_bubble.py -q`
  - `python -m pytest tests/test_stt_adapter.py tests/test_stt_recorder.py tests/test_chat_stt_flow.py -q`
```

Add real-device boundary:

```markdown
STT 自动化测试不依赖真实麦克风或真实转写服务；真实麦克风采集、真实 Whisper 服务和 STT / TTS 实时打断体验需要在本地设备上单独联调，并把失败日志写入平台日志。
```

- [ ] **Step 3: Update UI guidelines**

Add to `docs/ui-guidelines.md`:

```markdown
### 被动互动气泡

- 被动互动文本使用轻量气泡展示，必须与主对话框状态区分。
- 气泡显示时主对话框可隐藏；用户主动输入或开始语音输入时必须恢复主对话框。
- 气泡最大宽度、缩放和停留时长必须来自系统配置。

### STT 按钮状态

- STT 未启用时麦克风按钮禁用并提示“语音输入未启用”。
- 录音中按钮必须显示停止状态，输入框提示“正在听...”。
- 识别中输入框提示“正在识别...”，不得阻塞主线程。
```

- [ ] **Step 4: Update CLAUDE and README progress**

In `CLAUDE.md` and `docs/README.md`, mark Phase 5 as in progress and list implemented items:

```markdown
- 第五阶段：进行中
  - 系统设置显示参数扩展
  - 被动互动气泡
  - STT 配置、录音、转写与聊天主链路接入
```

- [ ] **Step 5: Run focused regression**

Run:

```bash
python -m pytest tests/test_config.py tests/test_settings_window.py tests/test_chat_window_scale.py tests/test_chat_passive_bubble.py tests/test_stt_adapter.py tests/test_stt_recorder.py tests/test_chat_stt_flow.py tests/test_chat_tts_flow.py -q
```

Expected: PASS.

- [ ] **Step 6: Run syntax checks**

Run:

```bash
python -m py_compile config/schema.py ui/settings/window.py ui/settings/pages/api_page.py ui/settings/pages/system_page.py ui/chat/window.py ui/chat/stt_recorder.py stt/types.py stt/adapter.py stt/adapters/openai_whisper.py stt/manager.py
```

Expected: PASS with no output.

- [ ] **Step 7: Run full test suite**

Run:

```bash
python -m pytest tests/ -q
```

Expected: PASS.

- [ ] **Step 8: Commit Task 7**

```bash
git add CLAUDE.md docs/README.md docs/architecture.md docs/development.md docs/ui-guidelines.md
git commit -m "docs: document phase5 ui and stt"
```

---

## Self-Review

- **Spec coverage:** Phase 5 的系统设置、聊天界面、被动互动、STT、STT / TTS 中断、配置化和验收标准均映射到 Task 1-7。
- **Placeholder scan:** 本计划没有未定内容或占位步骤；每个代码任务都有文件路径、测试片段、实现片段和验证命令。
- **Type consistency:** `ASRConfig`、`ChatDisplayConfig`、`PassiveInteractionConfig`、`STTResult`、`STTManager`、`STTRecorder` 在后续任务中的字段名与 Task 1 / Task 4 / Task 5 定义一致。
- **Residual risk:** OpenAI Whisper 真实服务、真实麦克风设备和长时间 STT / TTS 互锁体验无法完全用离线 pytest 覆盖，Task 7 已把真实设备联调边界写入开发文档。
