from pathlib import Path
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QLabel, QGridLayout, QPushButton, QStackedWidget,
)
from PySide6.QtGui import QPixmap, QIcon
from PySide6.QtCore import Qt, QSize
from core.character import load_character


class CharacterPage(QWidget):
    def __init__(self, characters_dir: Path, parent=None):
        super().__init__(parent)
        self._dir = characters_dir

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(16)

        title = QLabel("角色管理")
        title.setStyleSheet("font-size: 22px; font-weight: bold; color: #e8e8ed;")
        layout.addWidget(title)

        content = QHBoxLayout()
        content.setSpacing(20)

        # Left: character list
        self._list = QListWidget()
        self._list.setFixedWidth(200)
        self._list.setIconSize(QSize(40, 40))
        self._list.setStyleSheet("""
            QListWidget {
                background: rgba(255,255,255,0.03);
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 8px; padding: 8px; color: #e8e8ed;
            }
            QListWidget::item { padding: 10px 8px; border-radius: 6px; }
            QListWidget::item:selected { background: rgba(102, 126, 234, 0.2); }
            QListWidget::item:hover { background: rgba(255,255,255,0.04); }
        """)
        self._list.currentRowChanged.connect(self._on_select)
        content.addWidget(self._list)

        # Right: detail panel
        self._detail = QWidget()
        detail_layout = QVBoxLayout(self._detail)
        detail_layout.setContentsMargins(0, 0, 0, 0)
        detail_layout.setSpacing(12)

        self._char_name = QLabel()
        self._char_name.setStyleSheet("font-size: 18px; font-weight: bold; color: #e8e8ed;")
        detail_layout.addWidget(self._char_name)

        self._char_info = QLabel()
        self._char_info.setStyleSheet("color: #a0a0b0; font-size: 13px;")
        detail_layout.addWidget(self._char_info)

        # Sprite preview grid
        sprites_label = QLabel("立绘预览")
        sprites_label.setStyleSheet("color: #a0a0b0; font-size: 13px; margin-top: 8px;")
        detail_layout.addWidget(sprites_label)

        self._sprite_grid = QGridLayout()
        self._sprite_grid.setSpacing(8)
        self._sprite_container = QWidget()
        self._sprite_container.setLayout(self._sprite_grid)
        detail_layout.addWidget(self._sprite_container)

        detail_layout.addStretch()

        # Buttons
        btn_row = QHBoxLayout()
        open_btn = QPushButton("打开文件夹")
        open_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255,255,255,0.06); border: 1px solid rgba(255,255,255,0.1);
                border-radius: 6px; padding: 8px 16px; color: #e8e8ed; font-size: 13px;
            }
            QPushButton:hover { background: rgba(255,255,255,0.1); }
        """)
        open_btn.clicked.connect(self._open_folder)
        btn_row.addWidget(open_btn)
        btn_row.addStretch()
        detail_layout.addLayout(btn_row)

        content.addWidget(self._detail, 1)
        layout.addLayout(content, 1)

        self._char_dirs: list[Path] = []
        self._refresh()

    def _refresh(self):
        self._list.clear()
        self._char_dirs.clear()
        if not self._dir.is_dir():
            return
        for d in sorted(self._dir.iterdir()):
            if d.is_dir() and ((d / "prompt.md").exists() or (d / "SKILL.md").exists()):
                self._char_dirs.append(d)
                item = QListWidgetItem(d.name)
                # Try to use first sprite as icon
                sprites_dir = d / "sprites"
                if sprites_dir.is_dir():
                    for img in sprites_dir.glob("*.png"):
                        icon = QIcon(QPixmap(str(img)).scaled(40, 40, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
                        item.setIcon(icon)
                        break
                self._list.addItem(item)

    def _on_select(self, row: int):
        if row < 0 or row >= len(self._char_dirs):
            return
        char_dir = self._char_dirs[row]
        char = load_character(char_dir)
        self._char_name.setText(char.name)
        self._char_info.setText(f"情绪: {len(char.emotions)} 个  |  资源: {len(char.resources)} 个")

        # Clear old sprites
        while self._sprite_grid.count():
            w = self._sprite_grid.takeAt(0).widget()
            if w:
                w.deleteLater()

        # Show sprite thumbnails (max 12)
        sprites_dir = char_dir / "sprites"
        if sprites_dir.is_dir():
            for i, img in enumerate(sorted(sprites_dir.glob("*.png"))[:12]):
                lbl = QLabel()
                px = QPixmap(str(img)).scaled(64, 80, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                lbl.setPixmap(px)
                lbl.setToolTip(img.stem)
                lbl.setStyleSheet("background: rgba(255,255,255,0.03); border-radius: 4px; padding: 4px;")
                self._sprite_grid.addWidget(lbl, i // 6, i % 6)

    def _open_folder(self):
        row = self._list.currentRow()
        if row >= 0 and row < len(self._char_dirs):
            import subprocess
            subprocess.Popen(["explorer", str(self._char_dirs[row])])
