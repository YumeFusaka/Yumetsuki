from __future__ import annotations

from pathlib import Path
from threading import RLock

from config.schema import VisionConfig
from vision.ocr import create_ocr_adapter
from vision.screen_capture import capture_screen
from vision.types import OCRResult, ScreenRegion


class VisionManager:
    def __init__(self, config: VisionConfig, ocr_adapter=None):
        self._lock = RLock()
        self._config = self._snapshot_config(config)
        self._runtime_key = self._make_runtime_key(self._config)
        self._ocr = ocr_adapter or create_ocr_adapter(self._config)

    def update_config(self, config: VisionConfig) -> None:
        with self._lock:
            config_snapshot = self._snapshot_config(config)
            runtime_key = self._make_runtime_key(config_snapshot)
            runtime_changed = runtime_key != self._runtime_key
            self._config = config_snapshot
            if runtime_changed:
                self._ocr = create_ocr_adapter(config_snapshot)
                self._runtime_key = runtime_key

    @staticmethod
    def _snapshot_config(config: VisionConfig) -> VisionConfig:
        return config.model_copy(deep=True)

    @staticmethod
    def _make_runtime_key(config: VisionConfig) -> tuple[str, str]:
        return (config.ocr_engine, config.language)

    def capture_screen_image(self, region: ScreenRegion | None = None) -> OCRResult:
        with self._lock:
            enabled = self._config.enabled
            screenshot_dir = self._config.screenshot_dir
        if not enabled:
            return OCRResult(ok=False, error="视觉 OCR 未启用")
        try:
            image_path = capture_screen(screenshot_dir, region)
        except Exception as exc:
            return OCRResult(ok=False, error=f"屏幕截图失败：{exc}")
        return OCRResult(ok=True, image_path=str(image_path))

    def recognize_image_text(self, image_path: Path | str) -> OCRResult:
        with self._lock:
            ocr = self._ocr
            max_text_chars = self._config.max_text_chars
        result = ocr.recognize(Path(image_path))
        if not result.ok:
            return result
        return OCRResult(
            ok=True,
            text=result.summary(max_text_chars),
            image_path=result.image_path,
        )

    def capture_screen_text(self, region: ScreenRegion | None = None) -> OCRResult:
        capture = self.capture_screen_image(region)
        if not capture.ok:
            return capture
        return self.recognize_image_text(capture.image_path)
