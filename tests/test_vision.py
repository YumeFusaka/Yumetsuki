from pathlib import Path
from types import SimpleNamespace
import os
import time

from config.schema import VisionConfig
from vision.manager import VisionManager
import vision.ocr as ocr_module
from vision.ocr import PaddleOCRAdapter, RapidOCRAdapter, create_ocr_adapter
from vision.screen_capture import build_screenshot_path, cleanup_screenshots
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


def test_build_screenshot_path_uses_configured_dir(tmp_path):
    path = build_screenshot_path(str(tmp_path), now_text="20260526_120000")

    assert path == tmp_path / "screen_20260526_120000.png"


def test_build_screenshot_path_default_name_is_unique_for_high_frequency_capture(tmp_path):
    first = build_screenshot_path(str(tmp_path))
    second = build_screenshot_path(str(tmp_path))

    assert first != second
    assert first.name.startswith("screen_")
    assert first.suffix == ".png"


def test_cleanup_screenshots_removes_old_and_excess_files(tmp_path):
    now = time.time()
    recent_files = []
    for index in range(12):
        path = tmp_path / f"screen_20260528_12000{index}.png"
        path.write_text("x", encoding="utf-8")
        mtime = now - index * 60
        os.utime(path, (mtime, mtime))
        recent_files.append(path)
    old = tmp_path / "screen_20260527_000000.png"
    old.write_text("x", encoding="utf-8")
    old_mtime = now - 48 * 3600
    os.utime(old, (old_mtime, old_mtime))
    keep = tmp_path / "keep.png"
    keep.write_text("x", encoding="utf-8")

    removed = cleanup_screenshots(str(tmp_path), retention_hours=24, max_files=10, now=now)

    assert removed == 3
    assert all(path.exists() for path in recent_files[:10])
    assert not recent_files[10].exists()
    assert not recent_files[11].exists()
    assert not old.exists()
    assert keep.exists()


def test_vision_manager_runs_cleanup_before_capture(monkeypatch, tmp_path):
    old = tmp_path / "screen_old.png"
    old.write_text("old", encoding="utf-8")
    old_time = time.time() - 48 * 3600
    os.utime(old, (old_time, old_time))
    image = tmp_path / "screen_new.png"

    monkeypatch.setattr("vision.manager.capture_screen", lambda screenshot_dir, region=None: image)
    manager = VisionManager(VisionConfig(
        enabled=True,
        screenshot_dir=str(tmp_path),
        screenshot_retention_hours=24,
        screenshot_max_files=200,
        screenshot_cleanup_interval_minutes=30,
    ))

    result = manager.capture_screen_image()

    assert result.image_path == str(image)
    assert not old.exists()


def test_rapidocr_adapter_uses_optional_engine(monkeypatch, tmp_path):
    image = tmp_path / "screen.png"
    image.write_bytes(b"png")

    class FakeEngine:
        def __call__(self, image_path):
            return [([[0, 0], [1, 0], [1, 1], [0, 1]], "第一行", 0.98), ("第二行", 0.88)]

    adapter = RapidOCRAdapter(VisionConfig(), engine=FakeEngine())
    result = adapter.recognize(image)

    assert result.ok is True
    assert result.text == "第一行\n第二行"
    assert result.image_path == str(image)


def test_rapidocr_adapter_reads_v3_output_txts(tmp_path):
    image = tmp_path / "screen.png"
    image.write_bytes(b"png")

    class FakeEngine:
        def __call__(self, image_path):
            return SimpleNamespace(txts=["第一行", "第二行"])

    result = RapidOCRAdapter(VisionConfig(), engine=FakeEngine()).recognize(image)

    assert result.ok is True
    assert result.text == "第一行\n第二行"


def test_paddleocr_adapter_uses_optional_engine(tmp_path):
    image = tmp_path / "screen.png"
    image.write_bytes(b"png")

    class FakeEngine:
        def ocr(self, image_path, cls=True):
            return [[[[0, 0], [1, 0], [1, 1], [0, 1]], ("标题", 0.99)], [[[0, 2], [1, 2], [1, 3], [0, 3]], ("正文", 0.9)]]

    adapter = PaddleOCRAdapter(VisionConfig(), engine=FakeEngine())
    result = adapter.recognize(image)

    assert result.ok is True
    assert result.text == "标题\n正文"


def test_create_ocr_adapter_selects_rapidocr_by_default():
    adapter = create_ocr_adapter(VisionConfig())

    assert isinstance(adapter, RapidOCRAdapter)


def test_create_ocr_adapter_selects_paddleocr_for_advanced_engine():
    adapter = create_ocr_adapter(VisionConfig(ocr_engine="paddleocr"))

    assert isinstance(adapter, PaddleOCRAdapter)


def test_paddleocr_is_loaded_only_for_advanced_engine(monkeypatch):
    def fail_if_loaded(config):
        raise AssertionError("默认 RapidOCR 路径不应加载 PaddleOCR")

    monkeypatch.setattr(ocr_module, "_load_paddleocr_engine", fail_if_loaded)

    adapter = create_ocr_adapter(VisionConfig())

    assert isinstance(adapter, RapidOCRAdapter)


def test_paddleocr_is_not_a_default_requirement():
    requirements = Path("requirements.txt").read_text(encoding="utf-8").splitlines()

    assert not any(line.strip().lower().startswith("paddleocr") for line in requirements)
    assert any(line.strip().lower().startswith("rapidocr") for line in requirements)
    assert any(line.strip().lower().startswith("onnxruntime") for line in requirements)


def test_rapidocr_adapter_reports_missing_optional_dependency(monkeypatch, tmp_path):
    image = tmp_path / "screen.png"
    image.write_bytes(b"png")

    monkeypatch.setattr(
        "vision.ocr._load_rapidocr_engine",
        lambda config: (_ for _ in ()).throw(ImportError("missing rapidocr")),
    )

    result = RapidOCRAdapter(VisionConfig()).recognize(image)

    assert result.ok is False
    assert "rapidocr" in result.error.lower()


def test_rapidocr_adapter_caches_lazy_loaded_engine(monkeypatch, tmp_path):
    image = tmp_path / "screen.png"
    image.write_bytes(b"png")
    load_calls = []

    class FakeEngine:
        def __call__(self, image_path):
            return [([[0, 0], [1, 0], [1, 1], [0, 1]], "文本", 0.98)]

    def fake_load(config):
        load_calls.append(config.language)
        return FakeEngine()

    monkeypatch.setattr("vision.ocr._load_rapidocr_engine", fake_load)
    adapter = RapidOCRAdapter(VisionConfig())

    assert adapter.recognize(image).text == "文本"
    assert adapter.recognize(image).text == "文本"
    assert load_calls == ["ch"]


def test_paddleocr_adapter_caches_lazy_loaded_engine(monkeypatch, tmp_path):
    image = tmp_path / "screen.png"
    image.write_bytes(b"png")
    load_calls = []

    class FakeEngine:
        def ocr(self, image_path, cls=True):
            return [[[[0, 0], [1, 0], [1, 1], [0, 1]], ("标题", 0.99)]]

    def fake_load(config):
        load_calls.append(config.language)
        return FakeEngine()

    monkeypatch.setattr("vision.ocr._load_paddleocr_engine", fake_load)
    adapter = PaddleOCRAdapter(VisionConfig(ocr_engine="paddleocr", language="ch"))

    assert adapter.recognize(image).text == "标题"
    assert adapter.recognize(image).text == "标题"
    assert load_calls == ["ch"]


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


def test_vision_manager_update_config_rebuilds_adapter_when_ocr_runtime_changes():
    initial = VisionConfig(ocr_engine="rapidocr", language="ch")
    manager = VisionManager(initial)
    first_adapter = manager._ocr

    manager.update_config(VisionConfig(ocr_engine="rapidocr", language="en"))

    assert manager._config.language == "en"
    assert manager._ocr is not first_adapter


def test_vision_manager_keeps_config_snapshot_until_explicit_update(monkeypatch, tmp_path):
    image = tmp_path / "screen.png"
    image.write_bytes(b"png")
    captured = {}
    config = VisionConfig(enabled=True, screenshot_dir=str(tmp_path / "old"))
    manager = VisionManager(config, ocr_adapter=RapidOCRAdapter(config, engine=lambda _image: ["文本"]))
    config.enabled = False
    config.screenshot_dir = str(tmp_path / "new")

    def fake_capture(screenshot_dir, region=None):
        captured["screenshot_dir"] = screenshot_dir
        return image

    monkeypatch.setattr("vision.manager.capture_screen", fake_capture)

    result = manager.capture_screen_image()

    assert result.ok is True
    assert captured["screenshot_dir"] == str(tmp_path / "old")


def test_vision_manager_update_config_rebuilds_paddle_adapter_when_engine_changes():
    manager = VisionManager(VisionConfig(ocr_engine="rapidocr"))

    manager.update_config(VisionConfig(ocr_engine="paddleocr"))

    assert isinstance(manager._ocr, PaddleOCRAdapter)


def test_vision_manager_update_config_uses_non_runtime_fields_without_rebuilding(monkeypatch, tmp_path):
    image = tmp_path / "screen.png"
    image.write_bytes(b"png")
    captured = {}

    class FakeOCR:
        def recognize(self, image_path):
            return OCRResult(ok=True, text="abcdef", image_path=str(image_path))

    manager = VisionManager(
        VisionConfig(
            enabled=True,
            ocr_engine="rapidocr",
            language="ch",
            screenshot_dir=str(tmp_path / "old"),
            max_text_chars=10,
        ),
        ocr_adapter=FakeOCR(),
    )
    original_adapter = manager._ocr
    new_config = VisionConfig(
        enabled=True,
        ocr_engine="rapidocr",
        language="ch",
        screenshot_dir=str(tmp_path / "new"),
        max_text_chars=3,
    )

    def fake_capture(screenshot_dir, region=None):
        captured["screenshot_dir"] = screenshot_dir
        return image

    monkeypatch.setattr("vision.manager.capture_screen", fake_capture)
    manager.update_config(new_config)
    result = manager.capture_screen_text()

    assert manager._ocr is original_adapter
    assert captured["screenshot_dir"] == str(tmp_path / "new")
    assert result.text == "abc\n...(内容已截断)"
