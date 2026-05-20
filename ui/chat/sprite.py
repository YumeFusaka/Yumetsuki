from pathlib import Path
from PySide6.QtWidgets import QLabel
from PySide6.QtGui import QPixmap
from PySide6.QtCore import Qt
from core.character import Character, Emotion


class SpriteManager:
    def __init__(self, label: QLabel, char_dir: Path | None = None):
        self._label = label
        self._char_dir = char_dir
        self._emotions: list[Emotion] = []
        self._current: str | None = None

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
            pixmap = QPixmap(str(sprite_path))
            scaled = pixmap.scaled(
                self._label.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self._label.setPixmap(scaled)
            self._current = target.name

    def _find_emotion(self, name: str) -> Emotion | None:
        for e in self._emotions:
            if e.name == name or name in e.aliases:
                return e
        return self._emotions[0] if self._emotions else None
