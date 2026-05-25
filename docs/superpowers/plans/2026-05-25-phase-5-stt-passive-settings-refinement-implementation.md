# Phase 5 STT Passive Settings Refinement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 Phase 5 从 OpenAI Whisper 兼容 STT 与设置页被动开关，修正为 faster-whisper 本地服务、聊天窗运行态被动模式、系统字体下拉框和系统页独立保存。

**Architecture:** STT 保持 `STTManager -> STTAdapter` 抽象，但唯一有效适配器改为 `FasterWhisperAdapter`，通过本地 HTTP `/transcribe` 接口发送 WAV。被动互动从配置开关改为 `ChatWindow` 运行态状态机，由空闲计时器和右键菜单切换；系统设置页只保存系统配置，并通过 `SettingsWindow` 通知已打开的聊天窗应用新配置。

**Tech Stack:** Python 3、PySide6、pytest、requests、Pydantic、现有 YAML 配置系统。

---

## 文件结构

- 修改 `config/schema.py`
  - 收敛 `ASRConfig` 字段，默认引擎改为 `faster_whisper`。
  - `PassiveInteractionConfig` 删除系统级启用开关，新增 `idle_threshold_seconds`。
- 修改 `ui/settings/pages/api_page.py`
  - ASR 选项只保留 `none` 和 `faster_whisper`。
  - ASR URL 改为本地服务 `api_url`。
  - 删除 API Key / OpenAI Base URL 控件。
- 修改 `stt/manager.py`
  - 只识别 `none` 和 `faster_whisper`。
- 创建 `stt/adapters/faster_whisper.py`
  - 本地 faster-whisper HTTP 服务适配器。
- 删除 `stt/adapters/openai_whisper.py`
  - 移除 OpenAI SDK 适配路径。
- 修改 `ui/chat/window.py`
  - 新增被动状态运行态、空闲计时器、右键菜单切换、用户交互刷新、`apply_system_config()`。
- 修改 `ui/settings/pages/system_page.py`
  - 拆分布局组，字体改为系统字体下拉框，取消实时保存。
- 修改 `ui/settings/window.py`
  - 保存按钮同时支持 API 页和系统页，系统保存后应用到已打开聊天窗。
- 修改测试：
  - `tests/test_config.py`
  - `tests/test_settings_window.py`
  - `tests/test_stt_adapter.py`
  - `tests/test_chat_passive_bubble.py`
  - `tests/test_chat_stt_flow.py`
  - `tests/test_chat_window_scale.py`
- 修改文档：
  - `CLAUDE.md`
  - `docs/README.md`
  - `docs/architecture.md`
  - `docs/development.md`
  - `docs/ui-guidelines.md`
  - `.codex/operations-log.md`
  - `.codex/verification-report.md`

---

### Task 1: 配置模型改为 faster-whisper 与运行态被动阈值

**Files:**
- Modify: `config/schema.py`
- Test: `tests/test_config.py`

- [ ] **Step 1: Write the failing config tests**

Add or replace these tests in `tests/test_config.py`:

```python
def test_asr_config_defaults_to_faster_whisper_local_service():
    cfg = ASRConfig()

    assert cfg.engine == "faster_whisper"
    assert cfg.api_url == "http://127.0.0.1:8000"
    assert cfg.model == "base"
    assert cfg.language == "zh"
    assert not hasattr(cfg, "base_url")
    assert not hasattr(cfg, "api_key")
    assert not hasattr(cfg, "model_path")


def test_passive_interaction_config_uses_idle_threshold_not_enable_switch():
    cfg = SystemConfig()

    assert cfg.passive_interaction.idle_threshold_seconds == 300
    assert cfg.passive_interaction.bubble_max_width == 280
    assert cfg.passive_interaction.bubble_duration_seconds == 8
    assert not hasattr(cfg.passive_interaction, "enabled")
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```bash
python -m pytest tests/test_config.py::test_asr_config_defaults_to_faster_whisper_local_service tests/test_config.py::test_passive_interaction_config_uses_idle_threshold_not_enable_switch -q
```

Expected: FAIL because `ASRConfig` still defaults to `none` / `whisper-1` and `PassiveInteractionConfig.enabled` still exists.

- [ ] **Step 3: Implement schema changes**

Update `config/schema.py`:

```python
class ASRConfig(BaseModel):
    engine: str = "faster_whisper"
    api_url: str = "http://127.0.0.1:8000"
    model: str = "base"
    language: str = "zh"
    record_timeout_seconds: int = 20
    silence_threshold: float = 0.02
    silence_duration_ms: int = 1200


class PassiveInteractionConfig(BaseModel):
    idle_threshold_seconds: int = 300
    bubble_max_width: int = 280
    bubble_duration_seconds: int = 8
```

- [ ] **Step 4: Run config tests and verify GREEN**

Run:

```bash
python -m pytest tests/test_config.py -q
```

Expected: PASS.

---

### Task 2: API 页面 ASR 配置改为 faster-whisper 本地服务

**Files:**
- Modify: `ui/settings/pages/api_page.py`
- Test: `tests/test_settings_window.py`

- [ ] **Step 1: Write failing API page tests**

Replace the ASR Phase 5 test expectations in `tests/test_settings_window.py` with:

```python
def test_api_page_asr_uses_faster_whisper_local_service_fields():
    config = APIConfig()
    page = APIPage(config)

    assert [page._asr_engine.itemText(i) for i in range(page._asr_engine.count())] == ["none", "faster_whisper"]
    assert page._asr_url.placeholderText() == "http://127.0.0.1:8000"
    assert not hasattr(page, "_asr_base_url")
    assert not hasattr(page, "_asr_api_key")

    page._asr_engine.setCurrentText("faster_whisper")
    page._asr_url.setText("http://127.0.0.1:9000")
    page._asr_model.setText("small")
    page._asr_language.setCurrentText("auto")
    page._asr_timeout.setValue(15)
    page._asr_silence_threshold.setValue(3)
    page._asr_silence_duration.setValue(900)

    page.apply()

    assert config.asr.engine == "faster_whisper"
    assert config.asr.api_url == "http://127.0.0.1:9000"
    assert config.asr.model == "small"
    assert config.asr.language == "auto"
    assert config.asr.record_timeout_seconds == 15
    assert config.asr.silence_threshold == 0.03
    assert config.asr.silence_duration_ms == 900
```

- [ ] **Step 2: Run test and verify RED**

Run:

```bash
python -m pytest tests/test_settings_window.py::test_api_page_asr_uses_faster_whisper_local_service_fields -q
```

Expected: FAIL because the page still exposes `openai_whisper`, `base_url`, and `api_key`.

- [ ] **Step 3: Implement API page changes**

In `ui/settings/pages/api_page.py`, change the ASR group:

```python
self._asr_engine = QComboBox()
self._asr_engine.addItems(["none", "faster_whisper"])
self._asr_engine.setCurrentText(config.asr.engine)
asr_form.addRow("引擎:", self._asr_engine)

self._asr_url = QLineEdit(config.asr.api_url)
self._asr_url.setPlaceholderText("http://127.0.0.1:8000")
asr_form.addRow("本地服务:", self._asr_url)

self._asr_model = QLineEdit(config.asr.model)
self._asr_model.setPlaceholderText("base")
asr_form.addRow("模型:", self._asr_model)

self._asr_language = QComboBox()
self._asr_language.setEditable(True)
self._asr_language.addItems(["auto", *self.TTS_LANGUAGE_OPTIONS])
self._asr_language.setCurrentText(config.asr.language)
self._asr_language.setMaximumWidth(220)
asr_form.addRow("语言:", self._asr_language)
```

Update `apply()`:

```python
self._config.asr.engine = self._asr_engine.currentText()
self._config.asr.api_url = self._asr_url.text().strip()
self._config.asr.model = self._asr_model.text().strip()
self._config.asr.language = self._asr_language.currentText().strip()
self._config.asr.record_timeout_seconds = self._asr_timeout.value()
self._config.asr.silence_threshold = self._asr_silence_threshold.value() / 100.0
self._config.asr.silence_duration_ms = self._asr_silence_duration.value()
```

Update `reset()` similarly from `self._config.asr.api_url`.

- [ ] **Step 4: Run API settings tests**

Run:

```bash
python -m pytest tests/test_settings_window.py::test_api_page_asr_uses_faster_whisper_local_service_fields -q
```

Expected: PASS.

---

### Task 3: STT 适配器改为 FasterWhisperAdapter

**Files:**
- Create: `stt/adapters/faster_whisper.py`
- Modify: `stt/manager.py`
- Modify: `stt/adapters/__init__.py`
- Delete: `stt/adapters/openai_whisper.py`
- Test: `tests/test_stt_adapter.py`

- [ ] **Step 1: Write failing STT adapter tests**

Replace OpenAI Whisper tests in `tests/test_stt_adapter.py` with:

```python
def test_stt_manager_creates_faster_whisper_adapter_by_default():
    manager = STTManager(ASRConfig())

    assert manager._adapter.__class__.__name__ == "FasterWhisperAdapter"


def test_faster_whisper_adapter_sends_wav_to_local_service(monkeypatch):
    captured = {}

    class _Response:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {"text": "  你好呀  ", "language": "zh"}

    def fake_post(url, files=None, data=None, timeout=None):
        captured["url"] = url
        captured["files"] = files
        captured["data"] = data
        captured["timeout"] = timeout
        return _Response()

    monkeypatch.setattr("stt.adapters.faster_whisper.requests.post", fake_post)

    result = STTManager(
        ASRConfig(
            engine="faster_whisper",
            api_url="http://127.0.0.1:9000/",
            model="small",
            language="auto",
        )
    ).transcribe_wav(b"RIFF....WAVE")

    assert captured["url"] == "http://127.0.0.1:9000/transcribe"
    assert captured["data"] == {"model": "small", "language": "auto"}
    assert captured["files"]["file"][0] == "speech.wav"
    assert captured["files"]["file"][2] == "audio/wav"
    assert result.text == "你好呀"
    assert result.language == "zh"


def test_faster_whisper_adapter_returns_error_for_invalid_json(monkeypatch):
    class _Response:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {"segments": []}

    monkeypatch.setattr("stt.adapters.faster_whisper.requests.post", lambda **kwargs: _Response())

    result = STTManager(ASRConfig(engine="faster_whisper")).transcribe_wav(b"RIFF....WAVE")

    assert result.text == ""
    assert "返回格式无效" in result.error


def test_openai_whisper_is_not_supported():
    result = STTManager(ASRConfig(engine="openai_whisper")).transcribe_wav(b"RIFF....WAVE")

    assert result.text == ""
    assert "不支持的 STT 引擎" in result.error
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```bash
python -m pytest tests/test_stt_adapter.py -q
```

Expected: FAIL because `FasterWhisperAdapter` does not exist and `openai_whisper` is still supported.

- [ ] **Step 3: Implement FasterWhisperAdapter**

Create `stt/adapters/faster_whisper.py`:

```python
from __future__ import annotations

from io import BytesIO

import requests

from config.schema import ASRConfig
from stt.adapter import STTAdapter
from stt.types import STTResult


class FasterWhisperAdapter(STTAdapter):
    def __init__(self, config: ASRConfig):
        self._api_url = (config.api_url or "http://127.0.0.1:8000").rstrip("/")
        self._model = config.model or "base"
        self._language = config.language or "zh"
        self._timeout = max(1, int(config.record_timeout_seconds) + 10)

    def transcribe_wav(self, audio: bytes) -> STTResult:
        if not audio:
            return STTResult(text="", language=self._language, error="录音内容为空")

        wav_file = BytesIO(audio)
        wav_file.name = "speech.wav"
        try:
            response = requests.post(
                f"{self._api_url}/transcribe",
                files={"file": ("speech.wav", wav_file, "audio/wav")},
                data={"model": self._model, "language": self._language},
                timeout=self._timeout,
            )
            response.raise_for_status()
            payload = response.json()
        except Exception as exc:
            return STTResult(text="", language=self._language, error=str(exc))

        text = (payload.get("text") or "").strip() if isinstance(payload, dict) else ""
        if not text:
            return STTResult(text="", language=self._language, error="本地 STT 服务返回格式无效")
        return STTResult(text=text, language=payload.get("language") or self._language)
```

Update `stt/manager.py`:

```python
from config.schema import ASRConfig
from stt.adapters.faster_whisper import FasterWhisperAdapter
from stt.types import STTResult


class STTManager:
    def __init__(self, config: ASRConfig):
        self._adapter = self._create_adapter(config)

    @staticmethod
    def _create_adapter(config: ASRConfig):
        engine = (config.engine or "none").strip().lower()
        if engine == "none":
            return None
        if engine == "faster_whisper":
            return FasterWhisperAdapter(config)
        return engine
```

Delete `stt/adapters/openai_whisper.py`.

- [ ] **Step 4: Run STT adapter tests**

Run:

```bash
python -m pytest tests/test_stt_adapter.py -q
```

Expected: PASS.

---

### Task 4: 聊天窗被动状态状态机与右键菜单

**Files:**
- Modify: `ui/chat/window.py`
- Test: `tests/test_chat_passive_bubble.py`

- [ ] **Step 1: Write failing passive-state tests**

Add these tests to `tests/test_chat_passive_bubble.py`:

```python
def test_proactive_message_uses_main_panel_until_window_is_passive(monkeypatch):
    config = SystemConfig()
    config.passive_interaction.idle_threshold_seconds = 300

    window = _make_window(monkeypatch, config)
    try:
        window._on_proactive_message("主动提醒", "idle")

        assert window._passive_bubble.isHidden()
        assert not window._panel.isHidden()
        assert "主动提醒" in window._dialog_box.text()
    finally:
        window.close()


def test_proactive_message_uses_bubble_in_passive_state(monkeypatch):
    config = SystemConfig()
    window = _make_window(monkeypatch, config)
    try:
        window._enter_passive_state()
        window._on_proactive_message("被动提醒", "idle")

        assert not window._passive_bubble.isHidden()
        assert window._panel.isHidden()
        assert window._passive_bubble.text() == "被动提醒"
    finally:
        window.close()


def test_user_send_exits_passive_state(monkeypatch):
    config = SystemConfig()
    window = _make_window(monkeypatch, config)
    try:
        window._enter_passive_state()
        window._input.setText("你好")
        window._on_send()

        assert window._is_passive is False
        assert window._passive_bubble.isHidden()
        assert not window._panel.isHidden()
    finally:
        window.close()


def test_idle_timer_enters_passive_state(monkeypatch):
    config = SystemConfig()
    config.passive_interaction.idle_threshold_seconds = 1
    window = _make_window(monkeypatch, config)
    try:
        window._last_interaction_at -= 2
        window._check_passive_idle()

        assert window._is_passive is True
    finally:
        window.close()
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```bash
python -m pytest tests/test_chat_passive_bubble.py -q
```

Expected: FAIL because `ChatWindow` still uses `passive_interaction.enabled` and has no passive state machine.

- [ ] **Step 3: Implement passive state fields and timer**

In `ChatWindow.__init__()` add:

```python
import time

self._is_passive = False
self._last_interaction_at = time.monotonic()
self._passive_idle_timer = QTimer(self)
self._passive_idle_timer.setInterval(1000)
self._passive_idle_timer.timeout.connect(self._check_passive_idle)
self._passive_idle_timer.start()
```

Add methods:

```python
def _refresh_interaction(self) -> None:
    self._last_interaction_at = time.monotonic()
    self._exit_passive_state()

def _enter_passive_state(self) -> None:
    self._is_passive = True

def _exit_passive_state(self) -> None:
    self._is_passive = False
    self._hide_passive_bubble()

def _check_passive_idle(self) -> None:
    threshold = max(1, int(self._system_config.passive_interaction.idle_threshold_seconds))
    if time.monotonic() - self._last_interaction_at >= threshold:
        self._enter_passive_state()
```

Update `_on_proactive_message()`:

```python
def _on_proactive_message(self, message: str, source: str):
    """收到主动消息：以角色身份显示。"""
    if self._is_passive:
        self._show_passive_bubble(message)
        return
    if self._char_name:
        self._set_speaker_name(self._char_name)
    self._set_dialog_text(message)
```

- [ ] **Step 4: Refresh interaction in user actions**

Call `_refresh_interaction()` at the start of:

```python
def _on_send(self):
    self._refresh_interaction()
    ...

def _toggle_stt_recording(self) -> None:
    self._refresh_interaction()
    ...

def wheelEvent(self, event):
    self._refresh_interaction()
    ...

def mousePressEvent(self, event):
    self._refresh_interaction()
    ...

def _open_settings(self):
    self._refresh_interaction()
    ...
```

In `closeEvent()`, stop the idle timer:

```python
if hasattr(self, "_passive_idle_timer"):
    self._passive_idle_timer.stop()
```

- [ ] **Step 5: Add right-click menu toggle**

In `_show_context_menu()`:

```python
passive_action = menu.addAction("退出被动状态" if self._is_passive else "进入被动状态")
menu.addSeparator()
```

Handle action:

```python
elif action == passive_action:
    if self._is_passive:
        self._refresh_interaction()
    else:
        self._enter_passive_state()
```

- [ ] **Step 6: Run passive bubble tests**

Run:

```bash
python -m pytest tests/test_chat_passive_bubble.py -q
```

Expected: PASS.

---

### Task 5: 系统设置页字体下拉框、布局拆分和非实时保存

**Files:**
- Modify: `ui/settings/pages/system_page.py`
- Test: `tests/test_settings_window.py`

- [ ] **Step 1: Write failing system page tests**

Add tests:

```python
def test_system_page_uses_font_combo_with_system_fonts(monkeypatch):
    monkeypatch.setattr(
        "ui.settings.pages.system_page.QFontDatabase.families",
        lambda *_: ["Arial", "Microsoft YaHei", "SimSun"],
    )
    config = SystemConfig(font_family="Microsoft YaHei")

    page = SystemPage(config)

    assert page._font.isEditable()
    assert [page._font.itemText(i) for i in range(page._font.count())] == ["Arial", "Microsoft YaHei", "SimSun"]
    assert page._font.currentText() == "Microsoft YaHei"


def test_system_page_apply_does_not_save_until_settings_window_save(monkeypatch):
    saved = []
    monkeypatch.setattr("ui.settings.pages.system_page.ConfigManager.save_system", lambda self: saved.append("save"))

    config = SystemConfig()
    page = SystemPage(config)
    page._font.setCurrentText("Arial")
    page.apply()

    assert config.font_family == "Arial"
    assert saved == []
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```bash
python -m pytest tests/test_settings_window.py::test_system_page_uses_font_combo_with_system_fonts tests/test_settings_window.py::test_system_page_apply_does_not_save_until_settings_window_save -q
```

Expected: FAIL because `_font` is still a `QLineEdit` and `_save_live()` persists immediately.

- [ ] **Step 3: Implement font combo and grouped layout**

Update imports:

```python
from PySide6.QtGui import QFontDatabase
```

Add helper:

```python
def _font_families(current_font: str) -> list[str]:
    try:
        families = list(QFontDatabase.families())
    except Exception:
        families = []
    if current_font and current_font not in families:
        families.insert(0, current_font)
    if "Microsoft YaHei" not in families:
        families.append("Microsoft YaHei")
    return families
```

Create font combo:

```python
self._font = QComboBox()
self._font.setEditable(True)
self._font.addItems(_font_families(config.font_family))
self._font.setCurrentText(config.font_family)
basic_form.addRow("字体:", self._font)
```

Split groups:

```python
appearance = QGroupBox("基础外观")
display = QGroupBox("聊天显示")
passive = QGroupBox("被动状态")
network = QGroupBox("网络")
```

Move controls:

- `language`、`theme`、`font`、`font_size` into `appearance`
- `chat_font_scale`、`bubble_scale` into `display`
- `idle_threshold_seconds`、`bubble_max_width`、`bubble_duration` into `passive`
- `proxy` into `network`

Remove signal connections to `_save_live()`.

Update `apply()`:

```python
self._config.font_family = self._font.currentText().strip()
self._config.passive_interaction.idle_threshold_seconds = self._idle_threshold.value() * 60
```

- [ ] **Step 4: Run system page tests**

Run:

```bash
python -m pytest tests/test_settings_window.py::test_system_page_uses_font_combo_with_system_fonts tests/test_settings_window.py::test_system_page_apply_does_not_save_until_settings_window_save -q
```

Expected: PASS.

---

### Task 6: 设置中心系统页独立保存并应用到聊天窗

**Files:**
- Modify: `ui/settings/window.py`
- Modify: `ui/chat/window.py`
- Test: `tests/test_settings_window.py`
- Test: `tests/test_chat_window_scale.py`

- [ ] **Step 1: Write failing settings save tests**

Add to `tests/test_settings_window.py`:

```python
def test_save_button_visible_on_api_and_system_pages_only():
    _app()
    window = SettingsWindow()
    save_btn = next(
        button for button in window.findChildren(QPushButton)
        if button.objectName() == "save-config-button"
    )

    window._switch_page(0)
    assert not save_btn.isHidden()
    assert save_btn.text() == "保存 API 配置"

    window._switch_page(7)
    assert not save_btn.isHidden()
    assert save_btn.text() == "保存系统配置"

    window._switch_page(1)
    assert save_btn.isHidden()


def test_system_save_applies_to_existing_chat_window(monkeypatch):
    _app()
    applied = []

    window = SettingsWindow()
    window._chat_window = type(
        "Chat",
        (),
        {"apply_system_config": lambda self, config: applied.append(config.font_family)},
    )()
    monkeypatch.setattr("ui.settings.window.confirm_action", lambda *_: True)
    monkeypatch.setattr(window._config, "save_system", lambda: None)

    window._system_page._font.setCurrentText("Arial")
    window._switch_page(7)
    window._confirm_save()

    assert window._config.system.font_family == "Arial"
    assert applied == ["Arial"]
```

- [ ] **Step 2: Write failing ChatWindow apply test**

Add to `tests/test_chat_window_scale.py`:

```python
def test_chat_window_apply_system_config_updates_font_and_bubble(monkeypatch):
    window = _make_window(monkeypatch, SystemConfig(font_family="Microsoft YaHei", font_size=14))
    try:
        config = SystemConfig(font_family="Arial", font_size=18)
        config.chat_display.font_scale = 1.25
        config.chat_display.bubble_scale = 1.2
        config.passive_interaction.bubble_max_width = 360

        window.apply_system_config(config)

        assert window._display_font_family == "Arial"
        assert window._display_font_size == 18
        assert 'font-family: "Arial"' in window._input.styleSheet()
        assert window._passive_bubble.maximumWidth() <= 360
    finally:
        window.close()
```

- [ ] **Step 3: Run tests and verify RED**

Run:

```bash
python -m pytest tests/test_settings_window.py::test_save_button_visible_on_api_and_system_pages_only tests/test_settings_window.py::test_system_save_applies_to_existing_chat_window tests/test_chat_window_scale.py::test_chat_window_apply_system_config_updates_font_and_bubble -q
```

Expected: FAIL because save button only supports API page and `ChatWindow.apply_system_config()` does not exist.

- [ ] **Step 4: Implement settings window save routing**

In `_switch_page()`:

```python
self._save_btn.setVisible(index in {0, 7})
if index == 0:
    self._save_btn.setText("保存 API 配置")
elif index == 7:
    self._save_btn.setText("保存系统配置")
```

Add:

```python
def _apply_and_save_system(self):
    self._system_page.apply()
    self._config.save_system()
    if self._chat_window is not None and hasattr(self._chat_window, "apply_system_config"):
        self._chat_window.apply_system_config(self._config.system)
```

Update `_confirm_save()`:

```python
if self._stack.currentIndex() == 0:
    title = "确认保存"
    message = "确定保存当前 API 设定吗？"
    save = self._apply_and_save_api
    success = "API 设定已成功保存。"
elif self._stack.currentIndex() == 7:
    title = "确认保存"
    message = "确定保存当前系统设定吗？"
    save = self._apply_and_save_system
    success = "系统设定已成功保存。"
else:
    return
```

- [ ] **Step 5: Implement ChatWindow.apply_system_config()**

Add:

```python
def apply_system_config(self, config: SystemConfig) -> None:
    self._system_config = config
    self._display_font_family = config.font_family or SystemConfig().font_family
    self._display_font_size = max(1, int(config.font_size))
    self._display_font_scale = max(0.1, float(config.chat_display.font_scale))
    self._display_bubble_scale = max(0.1, float(config.chat_display.bubble_scale))
    self._apply_scale()
    if not self._passive_bubble.isHidden():
        self._position_passive_bubble()
```

- [ ] **Step 6: Run save and scale tests**

Run:

```bash
python -m pytest tests/test_settings_window.py tests/test_chat_window_scale.py -q
```

Expected: PASS.

---

### Task 7: 清理 OpenAI Whisper 引用与文档同步

**Files:**
- Modify: `CLAUDE.md`
- Modify: `docs/README.md`
- Modify: `docs/architecture.md`
- Modify: `docs/development.md`
- Modify: `docs/ui-guidelines.md`
- Modify: `.codex/operations-log.md`
- Modify: `.codex/verification-report.md`

- [ ] **Step 1: Write documentation checks**

Run after docs edits:

```bash
rg -n "OpenAIWhisperAdapter|openai_whisper|OpenAI Whisper 兼容|api_key.*ASR|base_url.*ASR" CLAUDE.md docs .codex
```

Expected after implementation: no matches except historical text inside old implementation plan if that file is intentionally retained.

- [ ] **Step 2: Update docs**

Document these facts:

- Phase 5 改进设计与计划已确认。
- STT 下一步只保留 faster-whisper 本地服务接口。
- 被动互动将从系统设置开关改为聊天窗运行态。
- 系统页保存语义将改为独立保存并保存后应用到聊天窗。
- 字体选择将改为系统字体下拉框。

- [ ] **Step 3: Update verification report**

Add a section with:

```markdown
## Phase 5 改进计划审查报告

- 需求匹配：覆盖 faster-whisper、本地被动状态、系统设置保存和字体下拉框。
- 架构一致：STT 保持适配器层；被动状态只影响 ChatWindow 运行态；系统页保存不污染 API 配置。
- 风险：真实 faster-whisper 服务仍需本地联调，离线测试只 mock HTTP。
- 建议：通过。
```

- [ ] **Step 4: Run docs scan**

Run:

```bash
rg -n "faster-whisper|faster_whisper|被动状态|保存系统配置|系统字体下拉框|Phase 5 改进" CLAUDE.md docs .codex
```

Expected: matches in updated docs.

---

### Task 8: Final verification

**Files:**
- All changed files

- [ ] **Step 1: Focused tests**

Run:

```bash
python -m pytest tests/test_config.py tests/test_settings_window.py tests/test_chat_window_scale.py tests/test_chat_passive_bubble.py tests/test_chat_stt_flow.py tests/test_stt_adapter.py tests/test_stt_recorder.py -q
```

Expected: PASS.

- [ ] **Step 2: Full tests**

Run:

```bash
python -m pytest tests/ -q
```

Expected: PASS.

- [ ] **Step 3: Syntax check**

Run:

```bash
python -m py_compile config/schema.py ui/settings/window.py ui/settings/pages/api_page.py ui/settings/pages/system_page.py ui/chat/window.py ui/chat/stt_recorder.py ui/theme.py stt/types.py stt/adapter.py stt/adapters/faster_whisper.py stt/manager.py tests/test_chat_stt_flow.py tests/test_stt_adapter.py tests/test_stt_recorder.py
```

Expected: exit code 0.

- [ ] **Step 4: Whitespace check**

Run:

```bash
git diff --check
```

Expected: exit code 0; LF/CRLF warnings are acceptable in this repository.

- [ ] **Step 5: Commit**

Stage only project changes, excluding local runtime configs:

```bash
git add .codex/operations-log.md .codex/verification-report.md CLAUDE.md config/schema.py docs/README.md docs/architecture.md docs/development.md docs/ui-guidelines.md docs/superpowers/plans/2026-05-25-phase-5-stt-passive-settings-refinement-implementation.md stt/adapters/faster_whisper.py stt/adapters/__init__.py stt/manager.py tests/test_chat_window_scale.py tests/test_chat_passive_bubble.py tests/test_config.py tests/test_settings_window.py tests/test_stt_adapter.py ui/chat/window.py ui/settings/pages/api_page.py ui/settings/pages/system_page.py ui/settings/window.py
git rm stt/adapters/openai_whisper.py
git commit -m "feat: refine phase 5 stt passive settings"
```

Do not stage:

```bash
data/config/agent.yaml
data/config/system_config.yaml
data/config/api.yaml
data/config/memory.yaml
```
