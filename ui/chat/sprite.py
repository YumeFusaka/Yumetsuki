from pathlib import Path
from PySide6.QtWidgets import QLabel
from PySide6.QtGui import QPixmap
from PySide6.QtCore import Qt, QSize
from core.character import Character, Emotion


class SpriteManager:
    MAX_PIXMAP_CACHE_ITEMS = 12

    def __init__(self, label: QLabel, char_dir: Path | None = None):
        self._label = label
        self._char_dir = char_dir
        self._emotions: list[Emotion] = []
        self._current: str | None = None
        self._current_path: Path | None = None
        self._original_pixmaps: dict[Path, QPixmap] = {}
        self._scaled_pixmaps: dict[tuple[Path, int, int], QPixmap] = {}

    def load_character(self, character: Character, char_dir: Path) -> None:
        self._char_dir = char_dir
        self._emotions = character.emotions
        if self._emotions:
            self.set_emotion("normal")

    def set_emotion(self, emotion: str | None) -> None:
        if not emotion or not self._char_dir:
            return
        target = self._find_emotion(emotion)
        if not target or target.name == self._current:
            return
        sprite_path = self._char_dir / "sprites" / target.sprite
        if sprite_path.exists():
            self._current_path = sprite_path
            self._current = target.name
            self._update_pixmap()

    def reload(self, size: QSize | None = None) -> None:
        """Reload current sprite, optionally at a specific size."""
        self._update_pixmap(size)

    def _update_pixmap(self, size: QSize | None = None) -> None:
        if not self._current_path or not self._current_path.exists():
            return
        pixmap = self._load_pixmap(self._current_path)
        if pixmap.isNull():
            return
        target_size = size or self._label.size()
        if target_size.width() > 0 and target_size.height() > 0:
            scaled = self._scaled_pixmap(pixmap, self._current_path, target_size)
            self._label.setPixmap(scaled)

    def _load_pixmap(self, path: Path) -> QPixmap:
        cached = self._original_pixmaps.get(path)
        if cached is not None:
            return cached
        pixmap = QPixmap(str(path))
        self._original_pixmaps[path] = pixmap
        self._trim_pixmap_cache()
        return pixmap

    def _scaled_pixmap(self, pixmap: QPixmap, path: Path, target_size: QSize) -> QPixmap:
        key = (path, target_size.width(), target_size.height())
        cached = self._scaled_pixmaps.get(key)
        if cached is not None:
            return cached
        scaled = pixmap.scaled(
            target_size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._scaled_pixmaps[key] = scaled
        self._trim_pixmap_cache()
        return scaled

    def _trim_pixmap_cache(self) -> None:
        while len(self._scaled_pixmaps) > self.MAX_PIXMAP_CACHE_ITEMS:
            first_key = next(iter(self._scaled_pixmaps))
            self._scaled_pixmaps.pop(first_key, None)

    def _find_emotion(self, name: str) -> Emotion | None:
        for e in self._emotions:
            if e.name == name or name in e.aliases:
                return e
        return self._emotions[0] if self._emotions else None
