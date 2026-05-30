from PySide6.QtCore import Signal
from PySide6.QtWidgets import QAbstractSpinBox, QHBoxLayout, QPushButton, QSpinBox, QVBoxLayout, QWidget

from ui.theme import SettingsFontTokens, settings_font_tokens


class RoseSpinBox(QWidget):
    """Theme-friendly spin box with explicit + / - controls."""

    valueChanged = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._spin = QSpinBox()
        self._spin.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self._spin.valueChanged.connect(self.valueChanged.emit)

        self._plus = QPushButton("+")
        self._minus = QPushButton("-")
        self._plus.setToolTip("增加")
        self._minus.setToolTip("减少")
        self._plus.clicked.connect(self.stepUp)
        self._minus.clicked.connect(self.stepDown)

        buttons = QVBoxLayout()
        buttons.setContentsMargins(0, 0, 0, 0)
        buttons.setSpacing(2)
        buttons.addWidget(self._plus)
        buttons.addWidget(self._minus)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addWidget(self._spin, 1)
        layout.addLayout(buttons)

        self.apply_settings_tokens(settings_font_tokens())

    def apply_settings_tokens(self, tokens: SettingsFontTokens) -> None:
        token_key = (tokens.family, tokens.body, tokens.button)
        if self.property("_settingsFontTokenKey") == token_key:
            return
        self.setStyleSheet(f"""
            QSpinBox {{
                background: rgba(255, 255, 255, 0.76);
                border: 1px solid rgba(220, 160, 180, 0.34);
                border-radius: 7px;
                padding: 7px 10px;
                color: #4a3040;
                font-size: {tokens.body}px;
                min-height: 20px;
            }}
            QSpinBox:focus {{
                border-color: #d4567a;
                background: rgba(255, 255, 255, 0.9);
            }}
            QPushButton {{
                background: rgba(255, 245, 250, 0.88);
                border: 1px solid rgba(212, 86, 122, 0.28);
                border-radius: 6px;
                color: #d4567a;
                font-size: {tokens.button}px;
                font-weight: 700;
                min-width: 22px;
                max-width: 22px;
                min-height: 15px;
                max-height: 15px;
                padding: 0;
            }}
            QPushButton:hover {{
                background: rgba(255, 200, 210, 0.62);
                border-color: rgba(212, 86, 122, 0.52);
                color: #9b3060;
            }}
            QPushButton:pressed {{
                background: rgba(212, 86, 122, 0.2);
            }}
        """)
        self.setProperty("_settingsFontTokenKey", token_key)

    def setRange(self, minimum: int, maximum: int) -> None:
        self._spin.setRange(minimum, maximum)

    def setValue(self, value: int) -> None:
        self._spin.setValue(value)

    def value(self) -> int:
        return self._spin.value()

    def setSuffix(self, suffix: str) -> None:
        self._spin.setSuffix(suffix)

    def stepUp(self) -> None:
        self._spin.stepUp()

    def stepDown(self) -> None:
        self._spin.stepDown()
