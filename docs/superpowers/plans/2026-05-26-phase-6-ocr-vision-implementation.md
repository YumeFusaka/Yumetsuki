# Phase 6 OCR Vision Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 增加屏幕 OCR 能力，并让显式触发的视觉文本进入当前会话短期上下文与后续代理回复。

**Architecture:** 第一版视觉能力只做 OCR 文本，不做复杂图像语义推理。新增 `vision/` 模块负责截图和 OCR；`SessionContext` 增加最近视觉观察列表；`AgentManager` 只在用户显式要求读屏时采集一次 OCR，并把结果注入本轮 prompt context。OCR 默认走可配置的 Tesseract 命令行适配器，不新增 Python OCR 依赖。

**Tech Stack:** Python 3、PySide6 screen capture、pytest、Pydantic、subprocess、现有 SessionContext / AgentManager。

---

## 文件结构

- 修改 `config/schema.py`
  - 新增 `VisionConfig`，挂到 `SystemConfig.vision`。
- 创建 `vision/__init__.py`
- 创建 `vision/types.py`
  - 定义 `ScreenRegion`、`OCRResult`、`VisualObservation`。
- 创建 `vision/screen_capture.py`
  - 使用 `QGuiApplication.primaryScreen().grabWindow(0)` 截图并保存到配置目录。
- 创建 `vision/ocr.py`
  - `TesseractOCRAdapter` 调用可配置命令：`tesseract <image> stdout -l <language> --psm <psm>`。
- 创建 `vision/manager.py`
  - `VisionManager.capture_screen_text()` 串联截图、OCR、截断和错误封装。
- 修改 `session/context.py`
  - 新增 `VisualObservation` 字段，保留最近视觉文本。
- 修改 `session/policy.py`
  - prompt context 中加入最近视觉观察。
- 修改 `session/store.py`
  - SQLite 快照保存 / 加载视觉观察，兼容旧库。
- 修改 `session/manager.py`
  - 增加 `record_visual_observation()`。
- 修改 `agent/manager.py`
  - 注入可选 `vision_manager`。
  - 仅在用户输入命中显式读屏关键词时采集 OCR 并写入当前 `SessionContext`。
- 修改测试：
  - `tests/test_config.py`
  - 新增 `tests/test_vision.py`
  - `tests/test_session_context.py`
  - `tests/test_session_store.py`
  - `tests/test_agent_manager.py`
- 修改文档：
  - `docs/architecture.md`
  - `docs/development.md`
  - 新增 `docs/vision-ocr.md`
  - `CLAUDE.md`

---

### Task 1: 增加 VisionConfig

**Files:**
- Modify: `config/schema.py`
- Test: `tests/test_config.py`

- [ ] **Step 1: Write failing config tests**

Add to `tests/test_config.py`:

```python
def test_vision_config_defaults():
    cfg = SystemConfig()

    assert cfg.vision.enabled is False
    assert cfg.vision.ocr_engine == "tesseract"
    assert cfg.vision.tesseract_cmd == "tesseract"
    assert cfg.vision.language == "chi_sim+eng"
    assert cfg.vision.psm == 6
    assert cfg.vision.screenshot_dir == "data/vision"
    assert cfg.vision.max_text_chars == 2000
    assert cfg.vision.explicit_trigger_only is True
```

- [ ] **Step 2: Run test and verify RED**

Run:

```bash
python -m pytest tests/test_config.py::test_vision_config_defaults -q
```

Expected: FAIL because `SystemConfig.vision` does not exist.

- [ ] **Step 3: Implement VisionConfig**

Update `config/schema.py`:

```python
class VisionConfig(BaseModel):
    enabled: bool = False
    ocr_engine: str = "tesseract"
    tesseract_cmd: str = "tesseract"
    language: str = "chi_sim+eng"
    psm: int = 6
    screenshot_dir: str = "data/vision"
    max_text_chars: int = 2000
    explicit_trigger_only: bool = True
```

Update `SystemConfig`:

```python
vision: VisionConfig = Field(default_factory=VisionConfig)
```

- [ ] **Step 4: Run config test**

Run:

```bash
python -m pytest tests/test_config.py::test_vision_config_defaults -q
```

Expected: PASS.

---

### Task 2: 定义视觉数据模型

**Files:**
- Create: `vision/__init__.py`
- Create: `vision/types.py`
- Test: `tests/test_vision.py`

- [ ] **Step 1: Write failing vision type tests**

Create `tests/test_vision.py`:

```python
from vision.types import OCRResult, ScreenRegion, VisualObservation


def test_ocr_result_success_summary_truncates_text():
    result = OCRResult(ok=True, text="第一行\n第二行", image_path="data/vision/a.png")

    assert result.summary(max_chars=4) == "第一行\n...(内容已截断)"


def test_visual_observation_prompt_line():
    obs = VisualObservation(
        text="屏幕上有错误提示",
        source="screen_ocr",
        image_path="data/vision/a.png",
        timestamp=1.0,
    )

    assert obs.to_prompt_line() == "screen_ocr: 屏幕上有错误提示"


def test_screen_region_as_qt_tuple():
    region = ScreenRegion(x=1, y=2, width=3, height=4)

    assert region.as_tuple() == (1, 2, 3, 4)
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```bash
python -m pytest tests/test_vision.py -q
```

Expected: FAIL because `vision.types` does not exist.

- [ ] **Step 3: Implement vision types**

Create `vision/__init__.py` as an empty package marker.

Create `vision/types.py`:

```python
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ScreenRegion:
    x: int
    y: int
    width: int
    height: int

    def as_tuple(self) -> tuple[int, int, int, int]:
        return (self.x, self.y, self.width, self.height)


@dataclass(frozen=True)
class OCRResult:
    ok: bool
    text: str = ""
    image_path: str = ""
    error: str = ""

    def summary(self, max_chars: int) -> str:
        text = self.text.strip()
        if max_chars > 0 and len(text) > max_chars:
            return text[:max_chars] + "\n...(内容已截断)"
        return text


@dataclass(frozen=True)
class VisualObservation:
    text: str
    source: str
    image_path: str
    timestamp: float

    def to_prompt_line(self) -> str:
        return f"{self.source}: {self.text}"
```

- [ ] **Step 4: Run vision type tests**

Run:

```bash
python -m pytest tests/test_vision.py -q
```

Expected: PASS.

---

### Task 3: 实现屏幕截图与 Tesseract OCR 适配器

**Files:**
- Create: `vision/screen_capture.py`
- Create: `vision/ocr.py`
- Test: `tests/test_vision.py`

- [ ] **Step 1: Write failing OCR adapter tests**

Append to `tests/test_vision.py`:

```python
from pathlib import Path

from config.schema import VisionConfig
from vision.ocr import TesseractOCRAdapter
from vision.screen_capture import build_screenshot_path


def test_build_screenshot_path_uses_configured_dir(tmp_path):
    path = build_screenshot_path(str(tmp_path), now_text="20260526_120000")

    assert path == tmp_path / "screen_20260526_120000.png"


def test_tesseract_adapter_invokes_configured_command(monkeypatch, tmp_path):
    image = tmp_path / "screen.png"
    image.write_bytes(b"png")
    captured = {}

    class Result:
        returncode = 0
        stdout = "  识别文本  \n"
        stderr = ""

    def fake_run(args, capture_output, text, encoding, timeout):
        captured["args"] = args
        captured["timeout"] = timeout
        return Result()

    monkeypatch.setattr("vision.ocr.subprocess.run", fake_run)

    adapter = TesseractOCRAdapter(VisionConfig(tesseract_cmd="tesseract.exe", language="chi_sim", psm=7))
    result = adapter.recognize(image)

    assert captured["args"] == ["tesseract.exe", str(image), "stdout", "-l", "chi_sim", "--psm", "7"]
    assert captured["timeout"] == 30
    assert result.ok is True
    assert result.text == "识别文本"


def test_tesseract_adapter_returns_error_on_failure(monkeypatch, tmp_path):
    image = tmp_path / "screen.png"
    image.write_bytes(b"png")

    class Result:
        returncode = 1
        stdout = ""
        stderr = "missing language"

    monkeypatch.setattr("vision.ocr.subprocess.run", lambda *args, **kwargs: Result())

    result = TesseractOCRAdapter(VisionConfig()).recognize(image)

    assert result.ok is False
    assert "missing language" in result.error
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```bash
python -m pytest tests/test_vision.py::test_build_screenshot_path_uses_configured_dir tests/test_vision.py::test_tesseract_adapter_invokes_configured_command tests/test_vision.py::test_tesseract_adapter_returns_error_on_failure -q
```

Expected: FAIL because screenshot and OCR modules do not exist.

- [ ] **Step 3: Implement screenshot path helper and capture function**

Create `vision/screen_capture.py`:

```python
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6.QtGui import QGuiApplication

from vision.types import ScreenRegion


def build_screenshot_path(screenshot_dir: str, now_text: str | None = None) -> Path:
    timestamp = now_text or datetime.now().strftime("%Y%m%d_%H%M%S")
    return Path(screenshot_dir) / f"screen_{timestamp}.png"


def capture_screen(screenshot_dir: str, region: ScreenRegion | None = None) -> Path:
    screen = QGuiApplication.primaryScreen()
    if screen is None:
        raise RuntimeError("未找到可用屏幕")
    pixmap = screen.grabWindow(0)
    if region is not None:
        pixmap = pixmap.copy(*region.as_tuple())
    path = build_screenshot_path(screenshot_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not pixmap.save(str(path), "PNG"):
        raise RuntimeError("屏幕截图保存失败")
    return path
```

- [ ] **Step 4: Implement TesseractOCRAdapter**

Create `vision/ocr.py`:

```python
from __future__ import annotations

from pathlib import Path
import subprocess

from config.schema import VisionConfig
from vision.types import OCRResult


class TesseractOCRAdapter:
    def __init__(self, config: VisionConfig):
        self._cmd = config.tesseract_cmd or "tesseract"
        self._language = config.language or "chi_sim+eng"
        self._psm = int(config.psm or 6)

    def recognize(self, image_path: Path) -> OCRResult:
        args = [
            self._cmd,
            str(image_path),
            "stdout",
            "-l",
            self._language,
            "--psm",
            str(self._psm),
        ]
        try:
            result = subprocess.run(
                args,
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=30,
            )
        except Exception as exc:
            return OCRResult(ok=False, image_path=str(image_path), error=str(exc))
        if result.returncode != 0:
            return OCRResult(ok=False, image_path=str(image_path), error=(result.stderr or "").strip())
        return OCRResult(ok=True, text=(result.stdout or "").strip(), image_path=str(image_path))
```

- [ ] **Step 5: Run OCR adapter tests**

Run:

```bash
python -m pytest tests/test_vision.py -q
```

Expected: PASS.

---

### Task 4: VisionManager 串联截图、OCR 与截断

**Files:**
- Create: `vision/manager.py`
- Test: `tests/test_vision.py`

- [ ] **Step 1: Write failing VisionManager tests**

Append to `tests/test_vision.py`:

```python
from vision.manager import VisionManager


def test_vision_manager_returns_disabled_error(tmp_path):
    manager = VisionManager(VisionConfig(enabled=False, screenshot_dir=str(tmp_path)))

    result = manager.capture_screen_text()

    assert result.ok is False
    assert "未启用" in result.error


def test_vision_manager_captures_and_truncates(monkeypatch, tmp_path):
    image = tmp_path / "screen.png"
    image.write_bytes(b"png")

    monkeypatch.setattr("vision.manager.capture_screen", lambda screenshot_dir, region=None: image)

    class FakeOCR:
        def recognize(self, image_path):
            return OCRResult(ok=True, text="abcdef", image_path=str(image_path))

    manager = VisionManager(
        VisionConfig(enabled=True, screenshot_dir=str(tmp_path), max_text_chars=3),
        ocr_adapter=FakeOCR(),
    )

    result = manager.capture_screen_text()

    assert result.ok is True
    assert result.text == "abc\n...(内容已截断)"
    assert result.image_path == str(image)
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```bash
python -m pytest tests/test_vision.py::test_vision_manager_returns_disabled_error tests/test_vision.py::test_vision_manager_captures_and_truncates -q
```

Expected: FAIL because `VisionManager` does not exist.

- [ ] **Step 3: Implement VisionManager**

Create `vision/manager.py`:

```python
from __future__ import annotations

from config.schema import VisionConfig
from vision.ocr import TesseractOCRAdapter
from vision.screen_capture import capture_screen
from vision.types import OCRResult, ScreenRegion


class VisionManager:
    def __init__(self, config: VisionConfig, ocr_adapter=None):
        self._config = config
        self._ocr = ocr_adapter or TesseractOCRAdapter(config)

    def capture_screen_text(self, region: ScreenRegion | None = None) -> OCRResult:
        if not self._config.enabled:
            return OCRResult(ok=False, error="视觉 OCR 未启用")
        try:
            image_path = capture_screen(self._config.screenshot_dir, region)
        except Exception as exc:
            return OCRResult(ok=False, error=str(exc))
        result = self._ocr.recognize(image_path)
        if not result.ok:
            return result
        return OCRResult(
            ok=True,
            text=result.summary(self._config.max_text_chars),
            image_path=result.image_path,
        )
```

- [ ] **Step 4: Run VisionManager tests**

Run:

```bash
python -m pytest tests/test_vision.py -q
```

Expected: PASS.

---

### Task 5: SessionContext 保存最近视觉观察

**Files:**
- Modify: `session/context.py`
- Modify: `session/policy.py`
- Modify: `session/manager.py`
- Modify: `session/store.py`
- Test: `tests/test_session_context.py`
- Test: `tests/test_session_store.py`

- [ ] **Step 1: Write failing session context tests**

Add to `tests/test_session_context.py`:

```python
from vision.types import VisualObservation


def test_session_context_prompt_includes_recent_visual_observation():
    ctx = SessionContext.new(session_id="s1", user_id="u1")
    ctx.visual_observations.append(VisualObservation(
        text="屏幕上显示登录失败",
        source="screen_ocr",
        image_path="data/vision/a.png",
        timestamp=1.0,
    ))

    prompt = SessionPolicy().build_prompt_context(ctx)

    assert "最近视觉信息" in prompt
    assert "screen_ocr: 屏幕上显示登录失败" in prompt
```

Add to `tests/test_session_store.py`:

```python
from vision.types import VisualObservation


def test_session_store_roundtrips_visual_observations(tmp_path):
    store = SessionContextStore(tmp_path / "session.db")
    ctx = SessionContext.new(session_id="s1", user_id="u1")
    ctx.visual_observations.append(VisualObservation(
        text="屏幕文字",
        source="screen_ocr",
        image_path="data/vision/a.png",
        timestamp=1.0,
    ))

    store.save(ctx)
    loaded = store.load("u1", "s1")

    assert loaded.visual_observations[0].text == "屏幕文字"
    assert loaded.visual_observations[0].source == "screen_ocr"
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```bash
python -m pytest tests/test_session_context.py::test_session_context_prompt_includes_recent_visual_observation tests/test_session_store.py::test_session_store_roundtrips_visual_observations -q
```

Expected: FAIL because `SessionContext.visual_observations` does not exist.

- [ ] **Step 3: Add visual observations to SessionContext**

Update `session/context.py`:

```python
from vision.types import VisualObservation
```

Update `SessionContext`:

```python
visual_observations: list[VisualObservation] = field(default_factory=list)
```

- [ ] **Step 4: Include visual observations in prompt context**

Update `session/policy.py`:

```python
if ctx.visual_observations:
    lines.append("- 最近视觉信息:")
    for obs in ctx.visual_observations[-3:]:
        lines.append(f"  - {obs.to_prompt_line()}")
```

- [ ] **Step 5: Add manager method**

Update `session/manager.py`:

```python
from vision.types import VisualObservation


def record_visual_observation(self, ctx: SessionContext, observation: VisualObservation) -> None:
    ctx.visual_observations.append(observation)
    ctx.visual_observations = ctx.visual_observations[-3:]
    if self._store:
        self._store.save(ctx)
```

- [ ] **Step 6: Persist visual observations**

Update `session/store.py` imports:

```python
from vision.types import VisualObservation
```

In `_init_db()`, after table creation, add a compatibility migration:

```python
columns = [row[1] for row in conn.execute("PRAGMA table_info(session_contexts)").fetchall()]
if "visual_observations_json" not in columns:
    conn.execute("ALTER TABLE session_contexts ADD COLUMN visual_observations_json TEXT DEFAULT '[]'")
```

Update `save()` SQL column list and values:

```python
"working_facts_json TEXT, active_tasks_json TEXT, visual_observations_json TEXT, "
```

Use:

```python
json.dumps([asdict(obs) for obs in ctx.visual_observations], ensure_ascii=False),
```

Update `load()` select:

```python
"SELECT turn_counter, summary_json, working_facts_json, active_tasks_json, visual_observations_json FROM session_contexts "
```

Load observations:

```python
ctx.visual_observations = [VisualObservation(**item) for item in json.loads(row[4] or "[]")]
```

- [ ] **Step 7: Run session tests**

Run:

```bash
python -m pytest tests/test_session_context.py tests/test_session_store.py -q
```

Expected: PASS.

---

### Task 6: AgentManager 显式触发 OCR 并注入会话态

**Files:**
- Modify: `agent/manager.py`
- Test: `tests/test_agent_manager.py`

- [ ] **Step 1: Write failing AgentManager vision tests**

Add to `tests/test_agent_manager.py`:

```python
from vision.types import OCRResult


class FakeVisionManager:
    def __init__(self):
        self.called = False

    def capture_screen_text(self):
        self.called = True
        return OCRResult(ok=True, text="屏幕上显示保存成功", image_path="data/vision/a.png")


def test_agent_manager_captures_screen_when_user_explicitly_asks():
    adapter = FakeStreamingAdapter(["知道了"])
    llm = LLMManager(LLMConfig(api_key="test"), adapter=adapter)
    session_manager = SessionContextManager()
    vision = FakeVisionManager()
    manager = AgentManager(
        llm,
        tool_registry=FakeToolRegistry(),
        session_manager=session_manager,
        session_id="s1",
        vision_manager=vision,
    )

    list(manager.chat_stream("帮我看看屏幕上写了什么"))

    ctx = session_manager.get_or_create("default-user", "s1")
    assert vision.called is True
    assert ctx.visual_observations[0].text == "屏幕上显示保存成功"


def test_agent_manager_does_not_capture_screen_for_normal_chat():
    adapter = FakeStreamingAdapter(["你好"])
    llm = LLMManager(LLMConfig(api_key="test"), adapter=adapter)
    vision = FakeVisionManager()
    manager = AgentManager(
        llm,
        tool_registry=FakeToolRegistry(),
        vision_manager=vision,
    )

    list(manager.chat_stream("你好呀"))

    assert vision.called is False
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```bash
python -m pytest tests/test_agent_manager.py::test_agent_manager_captures_screen_when_user_explicitly_asks tests/test_agent_manager.py::test_agent_manager_does_not_capture_screen_for_normal_chat -q
```

Expected: FAIL because `AgentManager` does not accept `vision_manager`.

- [ ] **Step 3: Add vision manager dependency and trigger helper**

Update `AgentManager.__init__()` signature:

```python
vision_manager=None,
```

Set:

```python
self._vision_manager = vision_manager
```

Add helper methods:

```python
def _should_capture_screen(self, user_input: str) -> bool:
    text = user_input.strip()
    triggers = ("看看屏幕", "看一下屏幕", "屏幕上", "读屏幕", "识别屏幕", "这个窗口")
    return any(trigger in text for trigger in triggers)

def _capture_visual_observation(self, session_ctx) -> None:
    if self._vision_manager is None:
        return
    result = self._vision_manager.capture_screen_text()
    if not result.ok or not result.text.strip():
        return
    from time import time
    from vision.types import VisualObservation

    self._session_manager.record_visual_observation(
        session_ctx,
        VisualObservation(
            text=result.text,
            source="screen_ocr",
            image_path=result.image_path,
            timestamp=time(),
        ),
    )
```

- [ ] **Step 4: Capture before building session prompt**

In `chat_stream()`, after `session_ctx` is created and user input is recorded:

```python
if self._should_capture_screen(user_input):
    self._capture_visual_observation(session_ctx)
```

- [ ] **Step 5: Run AgentManager tests**

Run:

```bash
python -m pytest tests/test_agent_manager.py -q
```

Expected: PASS.

---

### Task 7: 文档同步

**Files:**
- Create: `docs/vision-ocr.md`
- Modify: `docs/architecture.md`
- Modify: `docs/development.md`
- Modify: `CLAUDE.md`

- [ ] **Step 1: Create vision docs**

Create `docs/vision-ocr.md`:

```markdown
# OCR 与视觉输入

## 范围

Phase 6 第一版视觉能力只做屏幕 OCR 文本，不做复杂图像语义推理。

## 触发方式

默认仅在用户显式要求读屏时触发，例如“看看屏幕”“识别屏幕”“屏幕上写了什么”。

## 配置

`SystemConfig.vision` 字段：

- `enabled`：是否启用 OCR
- `ocr_engine`：当前为 `tesseract`
- `tesseract_cmd`：Tesseract 命令路径
- `language`：OCR 语言，如 `chi_sim+eng`
- `psm`：Tesseract page segmentation mode
- `screenshot_dir`：截图中间产物目录，默认 `data/vision`
- `max_text_chars`：进入会话态的最大文本长度
- `explicit_trigger_only`：是否只允许显式触发

## 隐私边界

截图和 OCR 文本来自用户当前屏幕，属于本地敏感运行期数据。`data/vision/` 默认不应提交。
```

- [ ] **Step 2: Update existing docs**

Document these facts:

- `vision/` 模块负责屏幕截图、OCR 和 `VisionManager`。
- `SessionContext` 可保存最近视觉观察，prompt context 只注入最近 3 条。
- Agent 只在显式读屏请求下触发 OCR。
- Tesseract 是本地外部可执行程序，计划不新增 Python OCR 依赖。

- [ ] **Step 3: Run docs scan**

Run:

```bash
rg -n "VisionConfig|vision/|OCR|Tesseract|显式触发|data/vision" CLAUDE.md docs
```

Expected: matches in updated docs.

---

### Task 8: Final verification

**Files:**
- All changed files

- [ ] **Step 1: Focused tests**

Run:

```bash
python -m pytest tests/test_config.py tests/test_vision.py tests/test_session_context.py tests/test_session_store.py tests/test_agent_manager.py -q
```

Expected: PASS.

- [ ] **Step 2: Syntax check**

Run:

```bash
python -m py_compile config/schema.py vision/__init__.py vision/types.py vision/screen_capture.py vision/ocr.py vision/manager.py session/context.py session/policy.py session/manager.py session/store.py agent/manager.py
```

Expected: exit code 0.

- [ ] **Step 3: Full tests**

Run:

```bash
python -m pytest tests/ -q
```

Expected: PASS.

- [ ] **Step 4: Diff check**

Run:

```bash
git diff --check
```

Expected: exit code 0.
