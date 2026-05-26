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
