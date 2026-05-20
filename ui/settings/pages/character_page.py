from pathlib import Path
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QLabel, QGridLayout, QPushButton, QTextEdit, QTabWidget, QScrollArea,
    QFileDialog, QMessageBox, QComboBox,
)
from PySide6.QtGui import QPixmap, QIcon
from PySide6.QtCore import Qt, QSize
from core.character import load_character
import shutil

CARD_STYLE = """
    QListWidget {
        background: rgba(255,255,255,0.5);
        border: 1px solid rgba(220, 160, 180, 0.25);
        border-radius: 8px; padding: 8px; color: #4a3040;
    }
    QListWidget::item { padding: 10px 8px; border-radius: 6px; color: #5a3050; }
    QListWidget::item:selected { background: rgba(255, 154, 162, 0.25); color: #9b3060; }
    QListWidget::item:hover { background: rgba(255, 200, 210, 0.2); }
"""

BTN_STYLE = """
    QPushButton {
        background: rgba(255,255,255,0.5); border: 1px solid rgba(220, 160, 180, 0.3);
        border-radius: 6px; padding: 8px 16px; color: #6b4a5a; font-size: 13px;
    }
    QPushButton:hover { background: rgba(255, 200, 210, 0.4); }
"""

TEXTEDIT_STYLE = """
    QTextEdit {
        background: rgba(255,255,255,0.6);
        border: 1px solid rgba(220, 160, 180, 0.25);
        border-radius: 6px; padding: 12px;
        color: #4a3040; font-size: 13px; font-family: 'Consolas', 'Microsoft YaHei';
    }
"""


class CharacterPage(QWidget):
    def __init__(self, characters_dir: Path, parent=None):
        super().__init__(parent)
        self._dir = characters_dir

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(16)

        title = QLabel("角色管理")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: #7a3a5a;")
        layout.addWidget(title)

        content = QHBoxLayout()
        content.setSpacing(16)

        # Left: character list
        left = QVBoxLayout()
        left.setSpacing(8)
        self._list = QListWidget()
        self._list.setFixedWidth(180)
        self._list.setIconSize(QSize(36, 36))
        self._list.setStyleSheet(CARD_STYLE)
        self._list.currentRowChanged.connect(self._on_select)
        left.addWidget(self._list, 1)

        import_btn = QPushButton("📥 导入 Skill")
        import_btn.setStyleSheet(BTN_STYLE)
        import_btn.clicked.connect(self._import_skill)
        left.addWidget(import_btn)

        open_btn = QPushButton("📂 打开文件夹")
        open_btn.setStyleSheet(BTN_STYLE)
        open_btn.clicked.connect(self._open_folder)
        left.addWidget(open_btn)
        content.addLayout(left)

        # Right: detail tabs
        self._tabs = QTabWidget()
        self._tabs.setStyleSheet("""
            QTabWidget::pane { border: none; background: transparent; }
            QTabBar::tab {
                background: rgba(255,255,255,0.3); color: #8c6b7a;
                padding: 8px 18px; border: none; border-bottom: 2px solid transparent;
            }
            QTabBar::tab:selected { color: #d4567a; border-bottom-color: #e88aaa; }
            QTabBar::tab:hover { color: #9b4d6a; }
        """)

        # Tab 1: Skill files
        skill_tab = QWidget()
        skill_layout = QVBoxLayout(skill_tab)
        skill_layout.setContentsMargins(0, 12, 0, 0)
        skill_layout.setSpacing(8)

        self._char_name = QLabel()
        self._char_name.setStyleSheet("font-size: 16px; font-weight: bold; color: #7a3a5a;")
        skill_layout.addWidget(self._char_name)

        self._char_info = QLabel()
        self._char_info.setStyleSheet("color: #8c6b7a; font-size: 12px;")
        skill_layout.addWidget(self._char_info)

        # File selector
        file_row = QHBoxLayout()
        file_label = QLabel("编辑文件:")
        file_label.setStyleSheet("color: #6b4a5a; font-size: 13px;")
        file_row.addWidget(file_label)
        self._file_combo = QComboBox()
        self._file_combo.setStyleSheet("""
            QComboBox {
                background: rgba(255,255,255,0.7); border: 1px solid rgba(220,160,180,0.3);
                border-radius: 6px; padding: 6px 12px; color: #4a3040; font-size: 13px;
            }
            QComboBox::drop-down { border: none; padding-right: 8px; }
            QComboBox QAbstractItemView {
                background: #fff5f7; border: 1px solid rgba(220,160,180,0.3);
                color: #4a3040; selection-background-color: rgba(255,154,162,0.3);
            }
        """)
        self._file_combo.currentIndexChanged.connect(self._on_file_changed)
        file_row.addWidget(self._file_combo, 1)
        skill_layout.addLayout(file_row)

        self._file_edit = QTextEdit()
        self._file_edit.setStyleSheet(TEXTEDIT_STYLE)
        skill_layout.addWidget(self._file_edit, 1)

        save_skill_btn = QPushButton("💾 保存文件")
        save_skill_btn.setStyleSheet(BTN_STYLE)
        save_skill_btn.clicked.connect(self._save_file)
        skill_layout.addWidget(save_skill_btn, alignment=Qt.AlignmentFlag.AlignRight)

        self._tabs.addTab(skill_tab, "Skill 文件")

        # Tab 2: Sprites
        sprite_tab = QWidget()
        sprite_layout = QVBoxLayout(sprite_tab)
        sprite_layout.setContentsMargins(0, 12, 0, 0)
        sprite_layout.setSpacing(8)

        sprite_header = QHBoxLayout()
        self._sprite_count = QLabel()
        self._sprite_count.setStyleSheet("color: #8c6b7a; font-size: 12px;")
        sprite_header.addWidget(self._sprite_count)
        sprite_header.addStretch()

        add_sprite_btn = QPushButton("+ 添加立绘")
        add_sprite_btn.setStyleSheet(BTN_STYLE)
        add_sprite_btn.clicked.connect(self._add_sprites)
        sprite_header.addWidget(add_sprite_btn)
        sprite_layout.addLayout(sprite_header)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        self._sprite_container = QWidget()
        self._sprite_grid = QGridLayout(self._sprite_container)
        self._sprite_grid.setSpacing(10)
        scroll.setWidget(self._sprite_container)
        sprite_layout.addWidget(scroll, 1)

        self._tabs.addTab(sprite_tab, "立绘管理")

        content.addWidget(self._tabs, 1)
        layout.addLayout(content, 1)

        self._char_dirs: list[Path] = []
        self._skill_files: list[Path] = []
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
                sprites_dir = d / "sprites"
                if sprites_dir.is_dir():
                    for img in sprites_dir.glob("*.png"):
                        icon = QIcon(QPixmap(str(img)).scaled(36, 36, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
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

        # Populate file combo with all .md and .yaml files
        self._file_combo.blockSignals(True)
        self._file_combo.clear()
        self._skill_files.clear()
        for f in sorted(char_dir.rglob("*.md")):
            self._skill_files.append(f)
            rel = f.relative_to(char_dir)
            self._file_combo.addItem(str(rel))
        for f in sorted(char_dir.rglob("*.yaml")):
            self._skill_files.append(f)
            rel = f.relative_to(char_dir)
            self._file_combo.addItem(str(rel))
        self._file_combo.blockSignals(False)
        if self._skill_files:
            self._file_combo.setCurrentIndex(0)
            self._on_file_changed(0)

        # Update sprites
        self._load_sprites(char_dir)

    def _on_file_changed(self, index: int):
        if index < 0 or index >= len(self._skill_files):
            return
        path = self._skill_files[index]
        try:
            self._file_edit.setPlainText(path.read_text(encoding="utf-8"))
        except Exception:
            self._file_edit.setPlainText("")

    def _save_file(self):
        index = self._file_combo.currentIndex()
        if index < 0 or index >= len(self._skill_files):
            return
        path = self._skill_files[index]
        path.write_text(self._file_edit.toPlainText(), encoding="utf-8")

    def _load_sprites(self, char_dir: Path):
        while self._sprite_grid.count():
            w = self._sprite_grid.takeAt(0).widget()
            if w:
                w.deleteLater()
        sprites_dir = char_dir / "sprites"
        count = 0
        if sprites_dir.is_dir():
            imgs = sorted(sprites_dir.glob("*.png"))
            count = len(imgs)
            for i, img in enumerate(imgs[:24]):
                frame = QWidget()
                frame_layout = QVBoxLayout(frame)
                frame_layout.setContentsMargins(4, 4, 4, 4)
                frame_layout.setSpacing(2)
                lbl = QLabel()
                px = QPixmap(str(img)).scaled(60, 75, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                lbl.setPixmap(px)
                lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
                frame_layout.addWidget(lbl)
                name_lbl = QLabel(img.stem)
                name_lbl.setStyleSheet("color: #6b4a5a; font-size: 10px;")
                name_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
                frame_layout.addWidget(name_lbl)
                frame.setStyleSheet("background: rgba(255,255,255,0.4); border-radius: 6px;")
                self._sprite_grid.addWidget(frame, i // 6, i % 6)
        self._sprite_count.setText(f"共 {count} 张立绘")

    def _add_sprites(self):
        row = self._list.currentRow()
        if row < 0:
            return
        files, _ = QFileDialog.getOpenFileNames(self, "选择立绘图片", "", "Images (*.png *.jpg *.webp)")
        if not files:
            return
        sprites_dir = self._char_dirs[row] / "sprites"
        sprites_dir.mkdir(exist_ok=True)
        for f in files:
            shutil.copy2(f, sprites_dir / Path(f).name)
        self._load_sprites(self._char_dirs[row])

    def _import_skill(self):
        """Import a skill folder (containing prompt.md, soul.md, resource/, etc.)"""
        folder = QFileDialog.getExistingDirectory(self, "选择 Skill 文件夹")
        if not folder:
            return
        src = Path(folder)
        name = src.name
        dest = self._dir / name
        if dest.exists():
            ret = QMessageBox.question(self, "确认", f"角色 '{name}' 已存在，是否覆盖？")
            if ret != QMessageBox.StandardButton.Yes:
                return
            shutil.rmtree(dest)
        shutil.copytree(src, dest)
        self._refresh()

    def _open_folder(self):
        row = self._list.currentRow()
        if row >= 0 and row < len(self._char_dirs):
            import subprocess
            subprocess.Popen(["explorer", str(self._char_dirs[row])])
