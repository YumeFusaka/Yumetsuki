from pathlib import Path
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QLabel, QGridLayout, QPushButton, QTextEdit, QTabWidget, QScrollArea,
    QFileDialog, QMessageBox, QInputDialog, QTreeWidget, QTreeWidgetItem,
    QDialog, QDialogButtonBox, QComboBox, QLineEdit, QFormLayout,
)
from PySide6.QtGui import QPixmap, QIcon
from PySide6.QtCore import Qt, QSize, QThread, Signal
from core.character import load_character
from config.manager import ConfigManager
from llm.adapters.openai_compat import OpenAICompatAdapter
import shutil
import yaml

CARD_STYLE = """
    QListWidget {
        background: rgba(255,255,255,0.5);
        border: 1px solid rgba(220, 160, 180, 0.25);
        border-radius: 8px; padding: 8px; color: #4a3040;
        outline: none;
    }
    QListWidget::item { padding: 8px 10px; border-radius: 6px; color: #5a3050; }
    QListWidget::item:selected { background: rgba(255, 154, 162, 0.25); color: #9b3060; border: 1px solid #d4567a; }
    QListWidget::item:hover { background: rgba(255, 200, 210, 0.2); }
    QListWidget:focus { border-color: #d4567a; }
"""

TREE_STYLE = """
    QTreeWidget {
        background: rgba(255,255,255,0.5);
        border: 1px solid rgba(220, 160, 180, 0.25);
        border-radius: 8px; padding: 6px; color: #4a3040;
        outline: none; font-size: 13px;
    }
    QTreeWidget::item { padding: 4px 6px; border-radius: 4px; color: #5a3050; }
    QTreeWidget::item:selected { background: rgba(255, 154, 162, 0.25); color: #9b3060; }
    QTreeWidget::item:hover { background: rgba(255, 200, 210, 0.15); }
    QTreeWidget:focus { border-color: #d4567a; }
    QTreeWidget::branch { background: transparent; }
    QHeaderView::section { background: rgba(255,220,230,0.3); color: #6b4a5a; border: none; padding: 4px 8px; }
"""

BTN_STYLE = """
    QPushButton {
        background: rgba(255,255,255,0.5); border: 1px solid rgba(220, 160, 180, 0.3);
        border-radius: 6px; padding: 8px 16px; color: #6b4a5a; font-size: 13px;
    }
    QPushButton:hover { background: rgba(255, 200, 210, 0.4); }
"""

BTN_DANGER = """
    QPushButton {
        background: rgba(255,220,220,0.5); border: 1px solid rgba(200, 100, 100, 0.3);
        border-radius: 6px; padding: 8px 16px; color: #8b3030; font-size: 13px;
    }
    QPushButton:hover { background: rgba(255, 180, 180, 0.5); }
"""

TEXTEDIT_STYLE = """
    QTextEdit {
        background: rgba(255,255,255,0.6);
        border: 1px solid rgba(220, 160, 180, 0.25);
        border-radius: 6px; padding: 12px;
        color: #4a3040; font-size: 13px; font-family: 'Consolas', 'Microsoft YaHei';
    }
    QTextEdit:focus { border-color: #d4567a; }
"""

DIALOG_STYLE = """
    QDialog {
        background: #fff5f7; color: #4a3040;
    }
    QLabel { color: #4a3040; font-size: 13px; }
    QLineEdit, QComboBox {
        background: rgba(255,255,255,0.8);
        border: 1px solid rgba(220,160,180,0.3);
        border-radius: 6px; padding: 6px 10px;
        color: #4a3040; font-size: 13px;
    }
    QLineEdit:focus, QComboBox:focus { border-color: #d4567a; }
    QPushButton {
        background: rgba(255,200,210,0.4);
        border: 1px solid rgba(220,160,180,0.3);
        border-radius: 6px; padding: 6px 16px;
        color: #6b4a5a; font-size: 13px;
    }
    QPushButton:hover { background: rgba(255,154,162,0.4); }
    QComboBox::drop-down { border: none; }
    QComboBox QAbstractItemView {
        background: #fff5f7; color: #4a3040;
        selection-background-color: rgba(255,154,162,0.3);
    }
"""

# Standard character directory structure
# 角色名/
# ├── prompt.md        (核心提示词)
# ├── soul.md          (灵魂设定)
# ├── SKILL.md         (技能说明)
# ├── sprites.yaml     (立绘配置)
# ├── resource/        (补充资料目录)
# │   └── *.md
# └── sprites/         (立绘图片目录)
#     └── *.png


class YamlSyncWorker(QThread):
    finished = Signal(str)

    def __init__(self, sprites_dir: Path, config):
        super().__init__()
        self._sprites_dir = sprites_dir
        self._config = config

    def run(self):
        files = sorted(f.name for f in self._sprites_dir.glob("*.png"))
        if not files:
            self.finished.emit("")
            return
        prompt = (
            "你是一个角色立绘情绪标注助手。根据以下立绘文件名列表，生成 sprites.yaml 内容。\n"
            "每个文件名（去掉.png后缀）就是情绪名。为每个情绪生成合理的 aliases（别名列表）。\n"
            "第一个情绪设为 default: true。\n\n"
            "文件列表：\n" + "\n".join(files) + "\n\n"
            "直接输出 YAML 内容，不要 ```yaml 标记，不要其他解释。格式示例：\n"
            "emotions:\n"
            "  - name: 平静\n"
            "    sprite: 平静.png\n"
            "    aliases: [普通, 正常, 默认]\n"
            "    default: true\n"
        )
        try:
            adapter = OpenAICompatAdapter(self._config)
            result = ""
            for chunk in adapter.stream_chat([
                {"role": "system", "content": "你是一个YAML生成助手，只输出YAML内容。"},
                {"role": "user", "content": prompt}
            ]):
                result += chunk
            self.finished.emit(result.strip())
        except Exception as e:
            self.finished.emit(f"# Error: {e}")


class NewFileDialog(QDialog):
    """Themed dialog for creating new files in the character directory."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("新建文件")
        self.setStyleSheet(DIALOG_STYLE)
        self.setMinimumWidth(350)

        layout = QFormLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        self._location = QComboBox()
        self._location.addItems(["根目录 (prompt/soul/SKILL)", "resource/ (补充资料)"])
        layout.addRow("位置:", self._location)

        self._name = QLineEdit()
        self._name.setPlaceholderText("文件名，如 notes.md")
        layout.addRow("文件名:", self._name)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def get_result(self):
        name = self._name.text().strip()
        if not name.endswith((".md", ".yaml")):
            name += ".md"
        if self._location.currentIndex() == 1:
            return f"resource/{name}"
        return name


class CharacterPage(QWidget):
    def __init__(self, characters_dir: Path, parent=None):
        super().__init__(parent)
        self._dir = characters_dir
        self._sync_worker = None

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
        self._list.setIconSize(QSize(36, 42))
        self._list.setStyleSheet(CARD_STYLE)
        self._list.currentRowChanged.connect(self._on_select)
        left.addWidget(self._list, 1)

        import_btn = QPushButton("📥 导入角色")
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
            QTabBar::tab:selected { color: #9b3060; border-bottom-color: #d4567a; }
            QTabBar::tab:hover { color: #9b4d6a; }
        """)

        # Tab 1: Skill files with tree structure
        skill_tab = QWidget()
        skill_layout = QVBoxLayout(skill_tab)
        skill_layout.setContentsMargins(0, 12, 0, 0)
        skill_layout.setSpacing(8)

        self._char_name_lbl = QLabel()
        self._char_name_lbl.setStyleSheet("font-size: 16px; font-weight: bold; color: #7a3a5a;")
        skill_layout.addWidget(self._char_name_lbl)

        # Directory structure info
        self._struct_info = QLabel(
            "📁 标准结构: prompt.md · soul.md · SKILL.md · sprites.yaml · resource/*.md · sprites/*.png"
        )
        self._struct_info.setStyleSheet("color: #8c6b7a; font-size: 11px; padding: 2px 0;")
        self._struct_info.setWordWrap(True)
        skill_layout.addWidget(self._struct_info)

        # File tree + editor
        file_area = QHBoxLayout()
        file_area.setSpacing(10)

        # File tree
        file_left = QVBoxLayout()
        file_left.setSpacing(6)
        self._file_tree = QTreeWidget()
        self._file_tree.setFixedWidth(200)
        self._file_tree.setHeaderLabels(["文件结构"])
        self._file_tree.setStyleSheet(TREE_STYLE)
        self._file_tree.currentItemChanged.connect(self._on_tree_select)
        file_left.addWidget(self._file_tree, 1)

        file_btn_row = QHBoxLayout()
        file_btn_row.setSpacing(4)
        add_file_btn = QPushButton("+ 新建")
        add_file_btn.setStyleSheet(BTN_STYLE)
        add_file_btn.clicked.connect(self._add_file)
        file_btn_row.addWidget(add_file_btn)

        del_file_btn = QPushButton("− 删除")
        del_file_btn.setStyleSheet(BTN_DANGER)
        del_file_btn.clicked.connect(self._del_file)
        file_btn_row.addWidget(del_file_btn)
        file_btn_row.addStretch()
        file_left.addLayout(file_btn_row)

        file_area.addLayout(file_left)

        # Editor
        editor_col = QVBoxLayout()
        editor_col.setSpacing(6)
        self._current_file_label = QLabel("未选择文件")
        self._current_file_label.setStyleSheet("color: #8c6b7a; font-size: 12px;")
        editor_col.addWidget(self._current_file_label)

        self._file_edit = QTextEdit()
        self._file_edit.setStyleSheet(TEXTEDIT_STYLE)
        editor_col.addWidget(self._file_edit, 1)

        save_file_btn = QPushButton("💾 保存")
        save_file_btn.setStyleSheet(BTN_STYLE)
        save_file_btn.clicked.connect(self._save_file)
        editor_col.addWidget(save_file_btn, alignment=Qt.AlignmentFlag.AlignRight)

        file_area.addLayout(editor_col, 1)
        skill_layout.addLayout(file_area, 1)

        self._tabs.addTab(skill_tab, "Skill 文件")

        # Tab 2: Sprites
        sprite_tab = QWidget()
        sprite_layout = QVBoxLayout(sprite_tab)
        sprite_layout.setContentsMargins(0, 12, 0, 0)
        sprite_layout.setSpacing(8)

        sprite_header = QHBoxLayout()
        self._sprite_count = QLabel()
        self._sprite_count.setStyleSheet("color: #6b4a5a; font-size: 12px;")
        sprite_header.addWidget(self._sprite_count)
        sprite_header.addStretch()

        sync_btn = QPushButton("🔄 AI同步YAML")
        sync_btn.setStyleSheet(BTN_STYLE)
        sync_btn.setToolTip("用LLM自动重建 sprites.yaml")
        sync_btn.clicked.connect(self._sync_yaml)
        sprite_header.addWidget(sync_btn)

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
        self._sprite_grid.setSpacing(8)
        scroll.setWidget(self._sprite_container)
        sprite_layout.addWidget(scroll, 1)

        self._tabs.addTab(sprite_tab, "立绘管理")

        content.addWidget(self._tabs, 1)
        layout.addLayout(content, 1)

        self._char_dirs: list[Path] = []
        self._current_file_path: Path | None = None
        self._refresh()

    def _refresh(self):
        self._list.clear()
        self._char_dirs.clear()
        if not self._dir.is_dir():
            return
        for d in sorted(self._dir.iterdir()):
            if d.is_dir() and (d / "prompt.md").exists():
                item = QListWidgetItem(self._character_icon(d), d.name)
                item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
                item.setSizeHint(QSize(150, 50))
                self._list.addItem(item)
                self._char_dirs.append(d)

    def _character_icon(self, char_dir: Path) -> QIcon:
        sprite_path = self._default_sprite_path(char_dir)
        if not sprite_path:
            return QIcon()
        pixmap = QPixmap(str(sprite_path))
        if pixmap.isNull():
            return QIcon()
        return QIcon(pixmap.scaled(
            36,
            42,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        ))

    def _default_sprite_path(self, char_dir: Path) -> Path | None:
        sprites_dir = char_dir / "sprites"
        yaml_path = char_dir / "sprites.yaml"
        if yaml_path.exists():
            try:
                data = yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}
            except yaml.YAMLError:
                data = {}
            emotions = data.get("emotions", [])
            for emotion in emotions:
                if emotion.get("default"):
                    path = sprites_dir / emotion.get("sprite", "")
                    if path.exists():
                        return path
            for emotion in emotions:
                path = sprites_dir / emotion.get("sprite", "")
                if path.exists():
                    return path
        if sprites_dir.is_dir():
            return next(iter(sorted(sprites_dir.glob("*.png"))), None)
        return None

    def _on_select(self, row: int):
        if row < 0 or row >= len(self._char_dirs):
            return
        char_dir = self._char_dirs[row]
        self._char_name_lbl.setText(char_dir.name)
        self._load_file_tree(char_dir)
        self._load_sprites(char_dir)

    def _load_file_tree(self, char_dir: Path):
        self._file_tree.clear()
        self._current_file_path = None
        self._file_edit.clear()
        self._current_file_label.setText("未选择文件")

        # Root files
        root_files = ["prompt.md", "soul.md", "SKILL.md", "sprites.yaml"]
        for fname in root_files:
            fpath = char_dir / fname
            item = QTreeWidgetItem([fname])
            item.setData(0, Qt.ItemDataRole.UserRole, str(fpath))
            if fpath.exists():
                item.setIcon(0, QIcon())
            else:
                item.setText(0, f"{fname} (不存在)")
            self._file_tree.addTopLevelItem(item)

        # resource/ folder
        resource_dir = char_dir / "resource"
        resource_node = QTreeWidgetItem(["📁 resource/"])
        resource_node.setData(0, Qt.ItemDataRole.UserRole, None)
        if resource_dir.is_dir():
            for f in sorted(resource_dir.glob("*.md")):
                child = QTreeWidgetItem([f.name])
                child.setData(0, Qt.ItemDataRole.UserRole, str(f))
                resource_node.addChild(child)
        self._file_tree.addTopLevelItem(resource_node)
        resource_node.setExpanded(True)

        # sprites/ folder (read-only info)
        sprites_dir = char_dir / "sprites"
        sprites_node = QTreeWidgetItem([f"📁 sprites/ ({len(list(sprites_dir.glob('*.png'))) if sprites_dir.is_dir() else 0} 张)"])
        sprites_node.setData(0, Qt.ItemDataRole.UserRole, None)
        self._file_tree.addTopLevelItem(sprites_node)

    def _on_tree_select(self, current, previous):
        if not current:
            return
        path_str = current.data(0, Qt.ItemDataRole.UserRole)
        if not path_str:
            self._current_file_path = None
            self._file_edit.clear()
            self._current_file_label.setText("(目录节点)")
            return
        path = Path(path_str)
        self._current_file_path = path
        self._current_file_label.setText(str(path.name))
        if path.exists():
            self._file_edit.setPlainText(path.read_text(encoding="utf-8"))
        else:
            self._file_edit.setPlainText("")

    def _save_file(self):
        if not self._current_file_path:
            return
        self._current_file_path.parent.mkdir(parents=True, exist_ok=True)
        self._current_file_path.write_text(self._file_edit.toPlainText(), encoding="utf-8")
        # Refresh tree to update "(不存在)" labels
        row = self._list.currentRow()
        if row >= 0:
            self._load_file_tree(self._char_dirs[row])

    def _add_file(self):
        char_row = self._list.currentRow()
        if char_row < 0:
            return
        dlg = NewFileDialog(self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        rel_path = dlg.get_result()
        char_dir = self._char_dirs[char_row]
        new_path = char_dir / rel_path
        new_path.parent.mkdir(parents=True, exist_ok=True)
        new_path.write_text("", encoding="utf-8")
        self._load_file_tree(char_dir)

    def _del_file(self):
        if not self._current_file_path or not self._current_file_path.exists():
            return
        # Don't allow deleting core files
        name = self._current_file_path.name
        dlg = QMessageBox(self)
        dlg.setStyleSheet(DIALOG_STYLE)
        dlg.setWindowTitle("确认删除")
        dlg.setText(f"确定删除 {name}？")
        dlg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if dlg.exec() != QMessageBox.StandardButton.Yes:
            return
        self._current_file_path.unlink(missing_ok=True)
        self._current_file_path = None
        self._file_edit.clear()
        char_row = self._list.currentRow()
        if char_row >= 0:
            self._load_file_tree(self._char_dirs[char_row])

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
            for i, img in enumerate(imgs):
                frame = QWidget()
                frame_layout = QVBoxLayout(frame)
                frame_layout.setContentsMargins(4, 4, 4, 4)
                frame_layout.setSpacing(4)

                lbl = QLabel()
                px = QPixmap(str(img)).scaled(60, 75, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                lbl.setPixmap(px)
                lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
                frame_layout.addWidget(lbl)

                name_lbl = QLabel(img.stem)
                name_lbl.setStyleSheet("color: #5a3050; font-size: 10px;")
                name_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
                frame_layout.addWidget(name_lbl)

                del_btn = QPushButton("✕")
                del_btn.setFixedSize(20, 20)
                del_btn.setStyleSheet("""
                    QPushButton { background: rgba(200,80,80,0.15); border: none;
                        border-radius: 10px; color: #a03030; font-size: 11px; }
                    QPushButton:hover { background: rgba(200,80,80,0.3); }
                """)
                del_btn.clicked.connect(lambda checked, p=img, d=char_dir: self._del_sprite(p, d))
                frame_layout.addWidget(del_btn, alignment=Qt.AlignmentFlag.AlignCenter)

                frame.setStyleSheet("background: rgba(255,255,255,0.4); border-radius: 6px;")
                self._sprite_grid.addWidget(frame, i // 5, i % 5)
        self._sprite_count.setText(f"共 {count} 张立绘")

    def _del_sprite(self, img_path: Path, char_dir: Path):
        dlg = QMessageBox(self)
        dlg.setStyleSheet(DIALOG_STYLE)
        dlg.setWindowTitle("删除立绘")
        dlg.setText(f"确定删除 {img_path.name}？")
        dlg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if dlg.exec() != QMessageBox.StandardButton.Yes:
            return
        img_path.unlink(missing_ok=True)
        yaml_path = char_dir / "sprites.yaml"
        if yaml_path.exists():
            data = yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}
            emotions = data.get("emotions", [])
            data["emotions"] = [e for e in emotions if e.get("sprite") != img_path.name]
            yaml_path.write_text(yaml.dump(data, allow_unicode=True, default_flow_style=False), encoding="utf-8")
        self._load_sprites(char_dir)

    def _add_sprites(self):
        row = self._list.currentRow()
        if row < 0:
            return
        files, _ = QFileDialog.getOpenFileNames(self, "选择立绘图片", "", "Images (*.png *.jpg *.webp)")
        if not files:
            return
        char_dir = self._char_dirs[row]
        sprites_dir = char_dir / "sprites"
        sprites_dir.mkdir(exist_ok=True)
        for f in files:
            shutil.copy2(f, sprites_dir / Path(f).name)
        self._load_sprites(char_dir)

    def _sync_yaml(self):
        row = self._list.currentRow()
        if row < 0:
            return
        char_dir = self._char_dirs[row]
        sprites_dir = char_dir / "sprites"
        if not sprites_dir.is_dir():
            return
        config = ConfigManager().api.llm
        self._sync_worker = YamlSyncWorker(sprites_dir, config)
        self._sync_worker.finished.connect(lambda result, d=char_dir: self._on_yaml_synced(result, d))
        self._sync_worker.start()
        self._sprite_count.setText("🔄 正在用AI生成 sprites.yaml...")

    def _on_yaml_synced(self, result: str, char_dir: Path):
        if not result or result.startswith("# Error"):
            dlg = QMessageBox(self)
            dlg.setStyleSheet(DIALOG_STYLE)
            dlg.setWindowTitle("同步失败")
            dlg.setText(result or "无立绘文件")
            dlg.exec()
            return
        yaml_path = char_dir / "sprites.yaml"
        yaml_path.write_text(result, encoding="utf-8")
        self._sprite_count.setText("✅ sprites.yaml 已同步")
        self._load_sprites(char_dir)
        self._load_file_tree(char_dir)

    def _import_skill(self):
        folder = QFileDialog.getExistingDirectory(self, "选择角色文件夹")
        if not folder:
            return
        src = Path(folder)
        name = src.name
        dest = self._dir / name
        if dest.exists():
            dlg = QMessageBox(self)
            dlg.setStyleSheet(DIALOG_STYLE)
            dlg.setWindowTitle("确认")
            dlg.setText(f"角色 '{name}' 已存在，是否覆盖？")
            dlg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if dlg.exec() != QMessageBox.StandardButton.Yes:
                return
            shutil.rmtree(dest)
        shutil.copytree(src, dest)
        self._refresh()

    def _open_folder(self):
        row = self._list.currentRow()
        if row >= 0 and row < len(self._char_dirs):
            import subprocess
            subprocess.Popen(["explorer", str(self._char_dirs[row])])
