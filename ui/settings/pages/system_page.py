from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QLineEdit,
    QComboBox, QLabel, QGroupBox, QCheckBox,
)
from config.manager import ConfigManager
from config.schema import SystemConfig
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
""" + SAKURA_COMBO_BOX_STYLE


class SystemPage(QWidget):
    def __init__(self, config: SystemConfig, parent=None):
        super().__init__(parent)
        self._config = config
        self._mgr = ConfigManager()
        self.setStyleSheet(FORM_STYLE)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(16)

        title = QLabel("系统设置")
        title.setStyleSheet("font-size: 22px; font-weight: bold; color: #7a3a5a;")
        layout.addWidget(title)

        # Appearance
        appearance = QGroupBox("外观")
        app_form = QFormLayout(appearance)
        app_form.setSpacing(10)

        self._language = QComboBox()
        self._language.addItems(["zh-CN", "en-US", "ja-JP"])
        self._language.setCurrentText(config.language)
        self._language.currentTextChanged.connect(self._save_live)
        app_form.addRow("语言:", self._language)

        self._theme = QComboBox()
        self._theme.addItems(["sakura"])
        self._theme.setCurrentText("sakura")
        self._theme.currentTextChanged.connect(self._save_live)
        app_form.addRow("主题:", self._theme)

        self._font = QLineEdit(config.font_family)
        self._font.editingFinished.connect(self._save_live)
        app_form.addRow("字体:", self._font)

        self._font_size = RoseSpinBox()
        self._font_size.setRange(10, 24)
        self._font_size.setValue(config.font_size)
        self._font_size.setMinimumWidth(280)
        self._font_size.valueChanged.connect(self._save_live)
        app_form.addRow("字号:", self._font_size)

        self._chat_font_scale = RoseSpinBox()
        self._chat_font_scale.setRange(50, 200)
        self._chat_font_scale.setValue(int(config.chat_display.font_scale * 100))
        self._chat_font_scale.setMinimumWidth(280)
        self._chat_font_scale.setSuffix("%")
        self._chat_font_scale.valueChanged.connect(self._save_live)
        app_form.addRow("聊天字号倍率:", self._chat_font_scale)

        self._bubble_scale = RoseSpinBox()
        self._bubble_scale.setRange(50, 200)
        self._bubble_scale.setValue(int(config.chat_display.bubble_scale * 100))
        self._bubble_scale.setMinimumWidth(280)
        self._bubble_scale.setSuffix("%")
        self._bubble_scale.valueChanged.connect(self._save_live)
        app_form.addRow("气泡缩放:", self._bubble_scale)

        layout.addWidget(appearance)

        passive = QGroupBox("被动互动")
        passive_form = QFormLayout(passive)
        passive_form.setSpacing(10)

        self._passive_enabled = QCheckBox("启用被动互动")
        self._passive_enabled.setChecked(config.passive_interaction.enabled)
        self._passive_enabled.stateChanged.connect(self._save_live)
        passive_form.addRow("", self._passive_enabled)

        self._bubble_max_width = RoseSpinBox()
        self._bubble_max_width.setRange(120, 800)
        self._bubble_max_width.setValue(config.passive_interaction.bubble_max_width)
        self._bubble_max_width.setMinimumWidth(280)
        self._bubble_max_width.setSuffix(" px")
        self._bubble_max_width.valueChanged.connect(self._save_live)
        passive_form.addRow("气泡最大宽度:", self._bubble_max_width)

        self._bubble_duration = RoseSpinBox()
        self._bubble_duration.setRange(1, 60)
        self._bubble_duration.setValue(config.passive_interaction.bubble_duration_seconds)
        self._bubble_duration.setMinimumWidth(280)
        self._bubble_duration.setSuffix(" 秒")
        self._bubble_duration.valueChanged.connect(self._save_live)
        passive_form.addRow("气泡停留时长:", self._bubble_duration)

        layout.addWidget(passive)

        # Network
        network = QGroupBox("网络")
        net_form = QFormLayout(network)
        net_form.setSpacing(10)

        self._proxy = QLineEdit(config.proxy)
        self._proxy.setPlaceholderText("http://127.0.0.1:7890（留空不使用代理）")
        self._proxy.editingFinished.connect(self._save_live)
        net_form.addRow("HTTP 代理:", self._proxy)

        layout.addWidget(network)
        layout.addStretch()

    def apply(self) -> None:
        self._config.language = self._language.currentText()
        self._config.theme = self._theme.currentText()
        self._config.font_family = self._font.text()
        self._config.font_size = self._font_size.value()
        self._config.chat_display.font_scale = self._chat_font_scale.value() / 100.0
        self._config.chat_display.bubble_scale = self._bubble_scale.value() / 100.0
        self._config.passive_interaction.enabled = self._passive_enabled.isChecked()
        self._config.passive_interaction.bubble_max_width = self._bubble_max_width.value()
        self._config.passive_interaction.bubble_duration_seconds = self._bubble_duration.value()
        self._config.proxy = self._proxy.text()

    def _save_live(self) -> None:
        self.apply()
        self._mgr.system = self._config
        self._mgr.save_system()
