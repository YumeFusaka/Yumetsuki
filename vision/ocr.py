from __future__ import annotations

from pathlib import Path
from typing import Any

from config.schema import VisionConfig
from vision.types import OCRResult


def _load_rapidocr_engine(config: VisionConfig):
    try:
        from rapidocr import LangRec, RapidOCR
    except ImportError:
        from rapidocr_onnxruntime import RapidOCR

        return RapidOCR()

    lang = (config.language or "ch").strip().lower()
    try:
        params = {"Rec.lang_type": LangRec(lang)}
    except ValueError:
        params = {"Rec.lang_type": LangRec("ch")}
    return RapidOCR(params=params)


def _load_paddleocr_engine(config: VisionConfig):
    from paddleocr import PaddleOCR

    return PaddleOCR(use_angle_cls=True, lang=config.language or "ch")


def _extract_rapidocr_text(raw: Any) -> str:
    if hasattr(raw, "txts"):
        return _join_ocr_text_items(getattr(raw, "txts"))
    if isinstance(raw, tuple):
        raw = raw[0]
    if raw is None:
        return ""
    return _join_ocr_text_items(raw)


def _join_ocr_text_items(items: Any) -> str:
    if isinstance(items, str):
        return items.strip()
    if items is None:
        return ""
    lines: list[str] = []
    for item in items:
        if isinstance(item, str):
            lines.append(item.strip())
            continue
        if not isinstance(item, (list, tuple)):
            continue
        if len(item) >= 2 and isinstance(item[1], str):
            lines.append(item[1].strip())
            continue
        if item and isinstance(item[0], str):
            lines.append(item[0].strip())
    return "\n".join(line for line in lines if line)


def _extract_paddleocr_text(raw: Any) -> str:
    lines: list[str] = []
    _collect_paddle_text(raw, lines)
    return "\n".join(line for line in lines if line)


def _collect_paddle_text(value: Any, lines: list[str]) -> None:
    if not isinstance(value, (list, tuple)):
        return
    if len(value) >= 2:
        text_info = value[1]
        if isinstance(text_info, str):
            lines.append(text_info.strip())
            return
        if isinstance(text_info, (list, tuple)) and text_info and isinstance(text_info[0], str):
            lines.append(text_info[0].strip())
            return
    for child in value:
        _collect_paddle_text(child, lines)


class RapidOCRAdapter:
    def __init__(self, config: VisionConfig, engine=None):
        self._config = config
        self._engine = engine

    def recognize(self, image_path: Path) -> OCRResult:
        try:
            if self._engine is None:
                self._engine = _load_rapidocr_engine(self._config)
            raw = self._engine(str(image_path))
            text = _extract_rapidocr_text(raw)
        except Exception as exc:
            return OCRResult(ok=False, image_path=str(image_path), error=f"RapidOCR 识别失败：{exc}")
        return OCRResult(ok=True, text=text, image_path=str(image_path))


class PaddleOCRAdapter:
    def __init__(self, config: VisionConfig, engine=None):
        self._config = config
        self._engine = engine

    def recognize(self, image_path: Path) -> OCRResult:
        try:
            if self._engine is None:
                self._engine = _load_paddleocr_engine(self._config)
            raw = self._engine.ocr(str(image_path), cls=True)
            text = _extract_paddleocr_text(raw)
        except Exception as exc:
            return OCRResult(ok=False, image_path=str(image_path), error=f"PaddleOCR 识别失败：{exc}")
        return OCRResult(ok=True, text=text, image_path=str(image_path))


def create_ocr_adapter(config: VisionConfig):
    engine = (config.ocr_engine or "rapidocr").strip().lower()
    if engine == "rapidocr":
        return RapidOCRAdapter(config)
    if engine == "paddleocr":
        return PaddleOCRAdapter(config)
    return RapidOCRAdapter(config)
