from __future__ import annotations

from PySide6.QtWidgets import QWidget


def longest_line_width(widget: QWidget, text: str) -> int:
    widget.ensurePolished()
    metrics = widget.fontMetrics()
    lines = str(text).splitlines() or [""]
    return max(metrics.horizontalAdvance(line) for line in lines)


def clamped_text_width(widget: QWidget, text: str, *, min_width: int, max_width: int, chrome_width: int) -> int:
    desired_width = longest_line_width(widget, text) + chrome_width
    return min(max_width, max(min_width, desired_width))
