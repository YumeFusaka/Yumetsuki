from PySide6.QtWidgets import QWidget, QVBoxLayout, QFormLayout, QLineEdit, QComboBox, QDoubleSpinBox, QSpinBox, QLabel
from config.schema import APIConfig


class APIPage(QWidget):
    def __init__(self, config: APIConfig, parent=None):
        super().__init__(parent)
        self._config = config
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        title = QLabel("API 设定")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: #e8e8ed;")
        layout.addWidget(title)

        form = QFormLayout()
        form.setSpacing(12)

        self._provider = QComboBox()
        self._provider.addItems(["openai_compat"])
        self._provider.setCurrentText(config.llm.provider)
        form.addRow("供应商:", self._provider)

        self._model = QLineEdit(config.llm.model)
        form.addRow("模型:", self._model)

        self._api_key = QLineEdit(config.llm.api_key)
        self._api_key.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("API Key:", self._api_key)

        self._base_url = QLineEdit(config.llm.base_url)
        form.addRow("Base URL:", self._base_url)

        self._temperature = QDoubleSpinBox()
        self._temperature.setRange(0.0, 2.0)
        self._temperature.setSingleStep(0.1)
        self._temperature.setValue(config.llm.temperature)
        form.addRow("Temperature:", self._temperature)

        self._max_tokens = QSpinBox()
        self._max_tokens.setRange(256, 32768)
        self._max_tokens.setValue(config.llm.max_tokens)
        form.addRow("Max Tokens:", self._max_tokens)

        # TTS section
        tts_title = QLabel("TTS 设定")
        tts_title.setStyleSheet("font-size: 16px; font-weight: bold; color: #e8e8ed; margin-top: 16px;")

        self._tts_engine = QComboBox()
        self._tts_engine.addItems(["none", "gptsovits"])
        self._tts_engine.setCurrentText(config.tts.engine)
        form.addRow(tts_title, None)
        form.addRow("TTS 引擎:", self._tts_engine)

        self._tts_url = QLineEdit(config.tts.api_url)
        form.addRow("TTS URL:", self._tts_url)

        layout.addLayout(form)
        layout.addStretch()

    def apply(self) -> None:
        self._config.llm.provider = self._provider.currentText()
        self._config.llm.model = self._model.text()
        self._config.llm.api_key = self._api_key.text()
        self._config.llm.base_url = self._base_url.text()
        self._config.llm.temperature = self._temperature.value()
        self._config.llm.max_tokens = self._max_tokens.value()
        self._config.tts.engine = self._tts_engine.currentText()
        self._config.tts.api_url = self._tts_url.text()
