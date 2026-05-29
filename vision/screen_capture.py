from __future__ import annotations

from datetime import datetime
from itertools import count
from pathlib import Path
import time

from vision.types import ScreenRegion

_SCREENSHOT_COUNTER = count()


def build_screenshot_path(screenshot_dir: str, now_text: str | None = None) -> Path:
    timestamp = now_text or (
        f"{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}_"
        f"{time.time_ns() % 1000000:06d}_{next(_SCREENSHOT_COUNTER):06d}"
    )
    return Path(screenshot_dir) / f"screen_{timestamp}.png"


def capture_screen(screenshot_dir: str, region: ScreenRegion | None = None) -> Path:
    try:
        from PIL import ImageGrab
    except ImportError as exc:
        raise RuntimeError("屏幕截图需要 Pillow ImageGrab 或 Tauri 截图入口") from exc

    bbox = None
    if region is not None:
        x, y, width, height = region.as_tuple()
        bbox = (x, y, x + width, y + height)

    path = build_screenshot_path(screenshot_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    image = ImageGrab.grab(bbox=bbox)
    try:
        image.save(str(path), "PNG")
    finally:
        image.close()
    return path


def cleanup_screenshots(
    screenshot_dir: str,
    retention_hours: int = 24,
    max_files: int = 200,
    now: float | None = None,
) -> int:
    root = Path(screenshot_dir)
    if not root.exists() or not root.is_dir():
        return 0
    cutoff = (now if now is not None else time.time()) - max(1, int(retention_hours)) * 3600
    files = sorted(
        (path for path in root.glob("screen_*.png") if path.is_file()),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    keep_by_count = set(files[:max(10, int(max_files))])
    removed = 0
    for path in files:
        try:
            if path.stat().st_mtime >= cutoff and path in keep_by_count:
                continue
            path.unlink()
            removed += 1
        except OSError:
            continue
    return removed
