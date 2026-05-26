from config.schema import VisionConfig
from vision.manager import VisionManager
from vision.ocr import TesseractOCRAdapter
from vision.screen_capture import build_screenshot_path
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
