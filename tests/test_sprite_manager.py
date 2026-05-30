from pathlib import Path

from PySide6.QtCore import QSize
from PySide6.QtGui import QColor, QPixmap
from PySide6.QtWidgets import QApplication, QLabel

from core.character import Character, Emotion
from ui.chat.sprite import SpriteManager


def _app() -> QApplication:
    app = QApplication.instance()
    return app or QApplication([])


def _write_sprite(path: Path) -> None:
    pixmap = QPixmap(80, 120)
    pixmap.fill(QColor("#ff9aaa"))
    pixmap.save(str(path))


def test_sprite_manager_caches_original_and_scaled_pixmaps(tmp_path):
    _app()
    sprites_dir = tmp_path / "sprites"
    sprites_dir.mkdir()
    sprite_path = sprites_dir / "normal.png"
    _write_sprite(sprite_path)

    label = QLabel()
    manager = SpriteManager(label)
    character = Character(
        name="测试角色",
        prompt="",
        skill="",
        soul="",
        emotions=[Emotion(name="normal", sprite="normal.png")],
    )

    manager.load_character(character, tmp_path)
    initial_scaled_count = len(manager._scaled_pixmaps)
    manager.reload(QSize(120, 180))
    after_first_explicit_size = len(manager._scaled_pixmaps)
    manager.reload(QSize(120, 180))

    assert len(manager._original_pixmaps) == 1
    assert after_first_explicit_size == initial_scaled_count + 1
    assert len(manager._scaled_pixmaps) == after_first_explicit_size


def test_sprite_manager_limits_scaled_pixmap_cache(tmp_path):
    _app()
    sprites_dir = tmp_path / "sprites"
    sprites_dir.mkdir()
    sprite_path = sprites_dir / "normal.png"
    _write_sprite(sprite_path)

    label = QLabel()
    manager = SpriteManager(label)
    character = Character(
        name="测试角色",
        prompt="",
        skill="",
        soul="",
        emotions=[Emotion(name="normal", sprite="normal.png")],
    )
    manager.load_character(character, tmp_path)

    for index in range(manager.MAX_PIXMAP_CACHE_ITEMS + 4):
        manager.reload(QSize(100 + index, 180 + index))

    assert len(manager._scaled_pixmaps) <= manager.MAX_PIXMAP_CACHE_ITEMS
