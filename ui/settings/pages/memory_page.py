from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from config.manager import ConfigManager
from config.schema import MemoryConfig
from core.model_catalog import (
    EMBEDDING_MODELS_DIR,
    is_embedding_model_dir,
    model_path_key,
    resolve_model_path,
    scan_model_dirs,
)
from ui.settings.feedback import confirm_action, show_feedback
from ui.theme import SAKURA_COMBO_BOX_STYLE
from ui.widgets.rose_spin_box import RoseSpinBox


FORM_STYLE = """
QLineEdit {
    background: rgba(255, 255, 255, 0.7);
    border: 1px solid rgba(220, 160, 180, 0.3);
    border-radius: 6px; padding: 8px 12px;
    color: #4a3040; font-size: 13px;
    min-height: 20px; min-width: 280px;
}
QLineEdit:focus {
    border-color: #d4567a;
    background: rgba(255, 255, 255, 0.85);
}
QLabel { color: #6b4a5a; font-size: 13px; }
QCheckBox {
    color: #4a3040;
    font-size: 13px;
    spacing: 8px;
}
QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border-radius: 4px;
    border: 1px solid rgba(220, 160, 180, 0.45);
    background: rgba(255,255,255,0.8);
}
QCheckBox::indicator:checked {
    background: #d4567a;
    border-color: #d4567a;
}
QGroupBox {
    color: #7a4060; font-size: 15px; font-weight: bold;
    border: 1px solid rgba(220, 160, 180, 0.2);
    border-radius: 10px; margin-top: 12px; padding: 20px 16px 12px 16px;
    background: rgba(255, 255, 255, 0.35);
}
QGroupBox::title { subcontrol-origin: margin; left: 16px; padding: 0 6px; }
QPushButton#browseBtn, QPushButton#deleteBtn {
    background: rgba(255, 255, 255, 0.8);
    border: 1px solid rgba(220, 160, 180, 0.34);
    border-radius: 6px; padding: 6px 14px;
    color: #6b4a5a; font-size: 13px;
}
QPushButton#browseBtn:hover, QPushButton#deleteBtn:hover {
    background: rgba(255, 225, 232, 0.92);
    border-color: rgba(212, 86, 122, 0.44);
}
""" + SAKURA_COMBO_BOX_STYLE

def _is_valid_model_dir(path: Path) -> bool:
    return is_embedding_model_dir(path)


def _scan_local_models() -> list[str]:
    return scan_model_dirs(EMBEDDING_MODELS_DIR, is_embedding_model_dir)


class MemoryPage(QWidget):
    def __init__(self, config: MemoryConfig, parent=None):
        super().__init__(parent)
        self._config = config
        self._mgr = ConfigManager()
        self.setStyleSheet(FORM_STYLE)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(16)

        title = QLabel("记忆设置")
        title.setStyleSheet("font-size: 22px; font-weight: bold; color: #7a3a5a;")
        layout.addWidget(title)

        desc = QLabel("本地记忆使用 Mem0 OSS，向量存储持久化在本机目录中。")
        desc.setStyleSheet("color: #8c6b7a; font-size: 13px;")
        layout.addWidget(desc)

        group = QGroupBox("本地记忆")
        form = QFormLayout(group)
        form.setSpacing(10)

        # 向量模型选择
        model_row = QHBoxLayout()
        self._model_combo = QComboBox()
        self._model_combo.setPlaceholderText("请选择向量模型...")
        self._refresh_model_list()
        if config.embedding_model_path:
            idx = self._find_model_path(config.embedding_model_path)
            if idx >= 0:
                self._model_combo.setCurrentIndex(idx)
            else:
                self._model_combo.addItem(config.embedding_model_path)
                self._model_combo.setCurrentText(config.embedding_model_path)
        self._model_combo.currentTextChanged.connect(self._save_live)
        model_row.addWidget(self._model_combo, 1)

        browse_btn = QPushButton("浏览...")
        browse_btn.setObjectName("browseBtn")
        browse_btn.clicked.connect(self._browse_model)
        model_row.addWidget(browse_btn)

        self._delete_btn = QPushButton("删除")
        self._delete_btn.setObjectName("deleteBtn")
        self._delete_btn.clicked.connect(self._delete_model)
        self._delete_btn.setEnabled(False)
        model_row.addWidget(self._delete_btn)

        self._model_combo.currentIndexChanged.connect(self._on_model_changed)
        form.addRow("向量模型:", model_row)

        # 启用开关
        self._enabled = QCheckBox("启用对话记忆（记住聊天内容，下次对话时自动回忆）")
        self._enabled.setChecked(config.enabled)
        self._enabled.stateChanged.connect(self._on_enabled_changed)
        form.addRow("", self._enabled)

        self._storage_dir = QLineEdit(config.storage_dir)
        self._storage_dir.editingFinished.connect(self._save_live)
        form.addRow("存储目录:", self._storage_dir)

        self._top_k = RoseSpinBox()
        self._top_k.setRange(1, 20)
        self._top_k.setValue(config.top_k)
        self._top_k.setMinimumWidth(140)
        self._top_k.valueChanged.connect(self._save_live)
        form.addRow("检索条数:", self._top_k)

        layout.addWidget(group)
        layout.addStretch()

    def _refresh_model_list(self) -> None:
        current = self._model_combo.currentText()
        self._model_combo.blockSignals(True)
        self._model_combo.clear()
        models = _scan_local_models()
        self._model_combo.addItems(models)
        # 记录哪些是 data/models 扫描的（不可删除）
        self._local_model_count = self._model_combo.count()
        if current and self._find_model_path(current) < 0:
            self._model_combo.addItem(current)
        if current:
            self._model_combo.setCurrentText(current)
        self._model_combo.blockSignals(False)

    def _on_model_changed(self) -> None:
        idx = self._model_combo.currentIndex()
        # 只允许删除非 data/models 扫描的条目
        deletable = idx >= self._local_model_count
        self._delete_btn.setEnabled(deletable)

    def _browse_model(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "选择向量模型目录")
        if not path:
            return
        if not _is_valid_model_dir(Path(path)):
            show_feedback(self, "无效模型", "所选目录不是有效的向量模型（缺少 config.json 或 modules.json）", success=False)
            return
        existing_index = self._find_model_path(path)
        if existing_index < 0:
            self._model_combo.addItem(path)
            existing_index = self._model_combo.count() - 1
        self._model_combo.setCurrentIndex(existing_index)

    def _find_model_path(self, path: str) -> int:
        if not path:
            return -1
        target_key = model_path_key(resolve_model_path(path, EMBEDDING_MODELS_DIR))
        for index in range(self._model_combo.count()):
            item_path = resolve_model_path(self._model_combo.itemText(index), EMBEDDING_MODELS_DIR)
            if model_path_key(item_path) == target_key:
                return index
        return -1

    def _delete_model(self) -> None:
        idx = self._model_combo.currentIndex()
        if idx < self._local_model_count:
            return
        self._model_combo.removeItem(idx)
        self._save_live()

    def _on_enabled_changed(self, state) -> None:
        enabling = state == Qt.CheckState.Checked.value
        if enabling:
            if not self._model_combo.currentText():
                show_feedback(self, "无法启用", "请先选择向量模型", success=False)
                self._enabled.blockSignals(True)
                self._enabled.setChecked(False)
                self._enabled.blockSignals(False)
                return
            ok = confirm_action(self, "启用对话记忆", "启用后将在本地保存对话记忆数据，是否继续？")
            if not ok:
                self._enabled.blockSignals(True)
                self._enabled.setChecked(False)
                self._enabled.blockSignals(False)
                return
        self._save_live()

    def apply(self) -> None:
        self._config.enabled = self._enabled.isChecked()
        self._config.storage_dir = self._storage_dir.text().strip() or "data/memory"
        self._config.embedding_model_path = self._model_combo.currentText()
        self._config.top_k = self._top_k.value()

    def _save_live(self) -> None:
        self.apply()
        self._mgr.memory = self._config
        self._mgr.save_memory()
