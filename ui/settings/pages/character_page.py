from pathlib import Path
from PySide6.QtWidgets import QWidget, QVBoxLayout, QListWidget, QLabel


class CharacterPage(QWidget):
    def __init__(self, characters_dir: Path, parent=None):
        super().__init__(parent)
        self._dir = characters_dir
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        title = QLabel("角色管理")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: #e8e8ed;")
        layout.addWidget(title)

        self._list = QListWidget()
        self._list.setStyleSheet("""
            QListWidget {
                background: rgba(255,255,255,0.03);
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 8px;
                padding: 8px;
                color: #e8e8ed;
            }
            QListWidget::item {
                padding: 8px 12px;
                border-radius: 6px;
            }
            QListWidget::item:selected {
                background: rgba(102, 126, 234, 0.3);
            }
        """)
        layout.addWidget(self._list)

        self._refresh()

    def _refresh(self):
        self._list.clear()
        if self._dir.is_dir():
            for d in sorted(self._dir.iterdir()):
                if d.is_dir() and (d / "prompt.md").exists() or (d / "SKILL.md").exists():
                    self._list.addItem(d.name)
