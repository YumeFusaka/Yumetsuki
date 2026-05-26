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
