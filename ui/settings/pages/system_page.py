from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QLineEdit,
    QComboBox, QSpinBox, QLabel, QGroupBox,
)
from config.schema import SystemConfig

FORM_STYLE = """
QLineEdit, QComboBox, QSpinBox {
    background: rgba(255, 255, 255, 0.7);
    border: 1px solid rgba(220, 160, 180, 0.3);
    border-radius: 6px; padding: 8px 12px;
    color: #4a3040; font-size: 13px;
    min-height: 20px; min-width: 280px;
}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus {
    border-color: #e88aaa;
    background: rgba(255, 255, 255, 0.85);
}
QComboBox::drop-down { border: none; padding-right: 8px; }
QComboBox QAbstractItemView {
    background: #fff5f7; border: 1px solid rgba(220, 160, 180, 0.3);
    color: #4a3040; selection-background-color: rgba(255, 154, 162, 0.3);
}
QLabel { color: #6b4a5a; font-size: 13px; }
QGroupBox {
    color: #7a4060; font-size: 15px; font-weight: bold;
    border: 1px solid rgba(220, 160, 180, 0.2);
    border-radius: 10px; margin-top: 12px; padding: 20px 16px 12px 16px;
    background: rgba(255, 255, 255, 0.35);
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
        title.setStyleSheet("font-size: 22px; font-weight: bold; color: #7a3a5a;")
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
        self._theme.addItems(["sakura", "dark"])
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
