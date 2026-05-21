from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from config.manager import ConfigManager
from config.schema import MemoryConfig
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
"""


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

        self._enabled = QCheckBox("启用本地记忆")
        self._enabled.setChecked(config.enabled)
        self._enabled.stateChanged.connect(self._save_live)
        form.addRow("", self._enabled)

        self._storage_dir = QLineEdit(config.storage_dir)
        self._storage_dir.editingFinished.connect(self._save_live)
        form.addRow("存储目录:", self._storage_dir)

        self._user_id = QLineEdit(config.user_id)
        self._user_id.editingFinished.connect(self._save_live)
        form.addRow("用户 ID:", self._user_id)

        self._top_k = RoseSpinBox()
        self._top_k.setRange(1, 20)
        self._top_k.setValue(config.top_k)
        self._top_k.setMinimumWidth(140)
        self._top_k.valueChanged.connect(self._save_live)
        form.addRow("检索条数:", self._top_k)

        layout.addWidget(group)
        layout.addStretch()

    def apply(self) -> None:
        self._config.enabled = self._enabled.isChecked()
        self._config.storage_dir = self._storage_dir.text().strip() or "data/memory"
        self._config.user_id = self._user_id.text().strip() or "default-user"
        self._config.top_k = self._top_k.value()

    def _save_live(self) -> None:
        self.apply()
        self._mgr.memory = self._config
        self._mgr.save_memory()
