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
            return text[:max_chars].rstrip() + "\n...(内容已截断)"
        return text


@dataclass(frozen=True)
class VisualObservation:
    text: str
    source: str
    image_path: str
    timestamp: float

    def to_prompt_line(self) -> str:
        return f"{self.source}: {self.text}"
