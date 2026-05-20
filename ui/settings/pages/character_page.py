from pathlib import Path
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QLabel, QGridLayout, QPushButton, QTextEdit, QTabWidget, QScrollArea,
    QFileDialog, QMessageBox,
)
from PySide6.QtGui import QPixmap, QIcon
from PySide6.QtCore import Qt, QSize
from core.character import load_character

CARD_STYLE = """
    QListWidget {
        background: rgba(255,255,255,0.03);
        border: 1px solid rgba(255,255,255,0.08);
        border-radius: 8px; padding: 8px; color: #e8e8ed;
    }
    QListWidget::item { padding: 10px 8px; border-radius: 6px; }
    QListWidget::item:selected { background: rgba(102, 126, 234, 0.2); }
    QListWidget::item:hover { background: rgba(255,255,255,0.04); }
"""

BTN_STYLE = """
    QPushButton {
        background: rgba(255,255,255,0.06); border: 1px solid rgba(255,255,255,0.1);
        border-radius: 6px; padding: 8px 16px; color: #e8e8ed; font-size: 13px;
    }
    QPushButton:hover { background: rgba(255,255,255,0.1); }
"""

TEXTEDIT_STYLE = """
    QTextEdit {
        background: rgba(255,255,255,0.03);
        border: 1px solid rgba(255,255,255,0.08);
        border-radius: 6px; padding: 12px;
        color: #e8e8ed; font-size: 13px; font-family: 'Consolas', 'Microsoft YaHei';
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
        title.setStyleSheet("font-size: 22px; font-weight: bold; color: #e8e8ed;")
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
                background: rgba(255,255,255,0.04); color: #a0a0b0;
                padding: 8px 18px; border: none; border-bottom: 2px solid transparent;
            }
            QTabBar::tab:selected { color: #e8e8ed; border-bottom-color: #667eea; }
            QTabBar::tab:hover { color: #e8e8ed; }
        """)

        # Tab 1: Skill/Prompt
        skill_tab = QWidget()
        skill_layout = QVBoxLayout(skill_tab)
        skill_layout.setContentsMargins(0, 12, 0, 0)
        skill_layout.setSpacing(8)

        self._char_name = QLabel()
        self._char_name.setStyleSheet("font-size: 16px; font-weight: bold; color: #e8e8ed;")
        skill_layout.addWidget(self._char_name)

        self._char_info = QLabel()
        self._char_info.setStyleSheet("color: #a0a0b0; font-size: 12px;")
        skill_layout.addWidget(self._char_info)

        prompt_label = QLabel("Prompt")
        prompt_label.setStyleSheet("color: #a0a0b0; font-size: 12px; margin-top: 8px;")
        skill_layout.addWidget(prompt_label)

        self._prompt_edit = QTextEdit()
        self._prompt_edit.setStyleSheet(TEXTEDIT_STYLE)
        self._prompt_edit.setMaximumHeight(150)
        skill_layout.addWidget(self._prompt_edit)

        soul_label = QLabel("Soul")
        soul_label.setStyleSheet("color: #a0a0b0; font-size: 12px;")
        skill_layout.addWidget(soul_label)

        self._soul_edit = QTextEdit()
        self._soul_edit.setStyleSheet(TEXTEDIT_STYLE)
        skill_layout.addWidget(self._soul_edit, 1)

        save_skill_btn = QPushButton("💾 保存 Skill")
        save_skill_btn.setStyleSheet(BTN_STYLE)
        save_skill_btn.clicked.connect(self._save_skill)
        skill_layout.addWidget(save_skill_btn, alignment=Qt.AlignmentFlag.AlignRight)

        self._tabs.addTab(skill_tab, "Skill / Prompt")

        # Tab 2: Sprites
        sprite_tab = QWidget()
        sprite_layout = QVBoxLayout(sprite_tab)
        sprite_layout.setContentsMargins(0, 12, 0, 0)
        sprite_layout.setSpacing(8)

        sprite_header = QHBoxLayout()
        self._sprite_count = QLabel()
        self._sprite_count.setStyleSheet("color: #a0a0b0; font-size: 12px;")
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

        # Load prompt/soul text
        prompt_path = char_dir / "prompt.md"
        self._prompt_edit.setPlainText(prompt_path.read_text(encoding="utf-8") if prompt_path.exists() else "")
        soul_path = char_dir / "soul.md"
        self._soul_edit.setPlainText(soul_path.read_text(encoding="utf-8") if soul_path.exists() else "")

        # Load sprites
        self._load_sprites(char_dir)

    def _load_sprites(self, char_dir: Path):
        while self._sprite_grid.count():
            w = self._sprite_grid.takeAt(0).widget()
            if w:
                w.deleteLater()

        sprites_dir = char_dir / "sprites"
        sprites = sorted(sprites_dir.glob("*.png")) if sprites_dir.is_dir() else []
        self._sprite_count.setText(f"共 {len(sprites)} 张立绘")

        for i, img in enumerate(sprites):
            cell = QVBoxLayout()
            lbl = QLabel()
            px = QPixmap(str(img)).scaled(72, 96, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            lbl.setPixmap(px)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet("background: rgba(255,255,255,0.03); border-radius: 6px; padding: 6px;")

            name_lbl = QLabel(img.stem)
            name_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            name_lbl.setStyleSheet("color: #a0a0b0; font-size: 11px;")

            container = QWidget()
            cl = QVBoxLayout(container)
            cl.setContentsMargins(0, 0, 0, 0)
            cl.setSpacing(4)
            cl.addWidget(lbl)
            cl.addWidget(name_lbl)

            self._sprite_grid.addWidget(container, i // 5, i % 5)

    def _save_skill(self):
        row = self._list.currentRow()
        if row < 0:
            return
        char_dir = self._char_dirs[row]
        (char_dir / "prompt.md").write_text(self._prompt_edit.toPlainText(), encoding="utf-8")
        (char_dir / "soul.md").write_text(self._soul_edit.toPlainText(), encoding="utf-8")

    def _add_sprites(self):
        row = self._list.currentRow()
        if row < 0:
            return
        char_dir = self._char_dirs[row]
        sprites_dir = char_dir / "sprites"
        sprites_dir.mkdir(exist_ok=True)

        files, _ = QFileDialog.getOpenFileNames(self, "选择立绘图片", "", "Images (*.png *.jpg *.webp)")
        if files:
            import shutil
            for f in files:
                shutil.copy2(f, sprites_dir / Path(f).name)
            self._load_sprites(char_dir)

    def _open_folder(self):
        row = self._list.currentRow()
        if row >= 0:
            import subprocess
            subprocess.Popen(["explorer", str(self._char_dirs[row])])
