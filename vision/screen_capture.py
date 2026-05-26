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
