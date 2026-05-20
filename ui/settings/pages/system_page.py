from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QLineEdit,
    QComboBox, QSpinBox, QLabel, QGroupBox,
)
from config.schema import SystemConfig

FORM_STYLE = """
QLineEdit, QComboBox, QSpinBox {
    background: rgba(255,255,255,0.04);
    border: 1px solid rgba(255,255,255,0.1);
    border-radius: 6px; padding: 8px 12px;
    color: #e8e8ed; font-size: 13px;
}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus { border-color: #667eea; }
QLabel { color: #a0a0b0; font-size: 13px; }
QGroupBox {
    color: #e8e8ed; font-size: 15px; font-weight: bold;
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 8px; margin-top: 12px; padding: 20px 16px 12px 16px;
}
QGroupBox::title { subcontrol-origin: margin; left: 16px; padding: 0 6px; }
"""


class SystemPage(QWidget):
    def __init__(self, config: SystemConfig, parent=None):
        super().__init__(parent)
        self._config = config
        self.setStyleSheet(FORM_STYLE)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(16)

        title = QLabel("系统设置")
        title.setStyleSheet("font-size: 22px; font-weight: bold; color: #e8e8ed;")
        layout.addWidget(title)

        # Appearance
        appearance = QGroupBox("外观")
        app_form = QFormLayout(appearance)
        app_form.setSpacing(10)

        self._language = QComboBox()
        self._language.addItems(["zh-CN", "en-US", "ja-JP"])
        self._language.setCurrentText(config.language)
        app_form.addRow("语言:", self._language)

        self._theme = QComboBox()
        self._theme.addItems(["dark", "light"])
        self._theme.setCurrentText(config.theme)
        app_form.addRow("主题:", self._theme)

        self._font = QLineEdit(config.font_family)
        app_form.addRow("字体:", self._font)

        self._font_size = QSpinBox()
        self._font_size.setRange(10, 24)
        self._font_size.setValue(config.font_size)
        app_form.addRow("字号:", self._font_size)

        layout.addWidget(appearance)

        # Network
        network = QGroupBox("网络")
        net_form = QFormLayout(network)
        net_form.setSpacing(10)

        self._proxy = QLineEdit(config.proxy)
        self._proxy.setPlaceholderText("http://127.0.0.1:7890（留空不使用代理）")
        net_form.addRow("HTTP 代理:", self._proxy)

        layout.addWidget(network)
        layout.addStretch()

    def apply(self) -> None:
        self._config.language = self._language.currentText()
        self._config.theme = self._theme.currentText()
        self._config.font_family = self._font.text()
        self._config.font_size = self._font_size.value()
        self._config.proxy = self._proxy.text()
