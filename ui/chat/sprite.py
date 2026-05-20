from pathlib import Path
from PySide6.QtWidgets import QLabel
from PySide6.QtGui import QPixmap
from PySide6.QtCore import Qt, QSize
from core.character import Character, Emotion


class SpriteManager:
    def __init__(self, label: QLabel, char_dir: Path | None = None):
        self._label = label
        self._char_dir = char_dir
        self._emotions: list[Emotion] = []
        self._current: str | None = None
        self._current_path: Path | None = None

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
        pixmap = QPixmap(str(self._current_path))
        target_size = size or self._label.size()
        if target_size.width() > 0 and target_size.height() > 0:
            scaled = pixmap.scaled(
                target_size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self._label.setPixmap(scaled)

    def _find_emotion(self, name: str) -> Emotion | None:
        for e in self._emotions:
            if e.name == name or name in e.aliases:
                return e
        return self._emotions[0] if self._emotions else None
