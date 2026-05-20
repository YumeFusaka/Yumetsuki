from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QLineEdit,
    QComboBox, QDoubleSpinBox, QSpinBox, QLabel, QGroupBox,
)
from config.schema import APIConfig

FORM_STYLE = """
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
    background: rgba(255, 255, 255, 0.7);
    border: 1px solid rgba(220, 160, 180, 0.3);
    border-radius: 6px;
    padding: 8px 12px;
    color: #4a3040;
    font-size: 13px;
    min-height: 20px;
    min-width: 280px;
}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {
    border-color: #e88aaa;
    background: rgba(255, 255, 255, 0.85);
}
QComboBox::drop-down {
    border: none;
    padding-right: 8px;
}
QComboBox QAbstractItemView {
    background: #fff5f7;
    border: 1px solid rgba(220, 160, 180, 0.3);
    color: #4a3040;
    selection-background-color: rgba(255, 154, 162, 0.3);
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


class APIPage(QWidget):
    def __init__(self, config: APIConfig, parent=None):
        super().__init__(parent)
        self._config = config
        self.setStyleSheet(FORM_STYLE)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(16)

        title = QLabel("API 设定")
        title.setStyleSheet("font-size: 22px; font-weight: bold; color: #7a3a5a;")
        layout.addWidget(title)

        # LLM Group
        llm_group = QGroupBox("LLM 大语言模型")
        llm_form = QFormLayout(llm_group)
        llm_form.setSpacing(10)

        self._provider = QComboBox()
        self._provider.addItems(["openai_compat"])
        self._provider.setCurrentText(config.llm.provider)
        llm_form.addRow("供应商:", self._provider)

        self._model = QLineEdit(config.llm.model)
        llm_form.addRow("模型:", self._model)

        self._api_key = QLineEdit(config.llm.api_key)
        self._api_key.setEchoMode(QLineEdit.EchoMode.Password)
        llm_form.addRow("API Key:", self._api_key)

        self._base_url = QLineEdit(config.llm.base_url)
        llm_form.addRow("Base URL:", self._base_url)

        self._temperature = QDoubleSpinBox()
        self._temperature.setRange(0.0, 2.0)
        self._temperature.setSingleStep(0.1)
        self._temperature.setValue(config.llm.temperature)
        llm_form.addRow("Temperature:", self._temperature)

        self._max_tokens = QSpinBox()
        self._max_tokens.setRange(256, 32768)
        self._max_tokens.setValue(config.llm.max_tokens)
        llm_form.addRow("Max Tokens:", self._max_tokens)

        layout.addWidget(llm_group)

        # TTS Group
        tts_group = QGroupBox("TTS 语音合成")
        tts_form = QFormLayout(tts_group)
        tts_form.setSpacing(10)

        self._tts_engine = QComboBox()
        self._tts_engine.addItems(["none", "gptsovits", "cosyvoice"])
        self._tts_engine.setCurrentText(config.tts.engine)
        tts_form.addRow("引擎:", self._tts_engine)

        self._tts_url = QLineEdit(config.tts.api_url)
        tts_form.addRow("API URL:", self._tts_url)

        layout.addWidget(tts_group)

        # ASR Group
        asr_group = QGroupBox("ASR 语音识别")
        asr_form = QFormLayout(asr_group)
        asr_form.setSpacing(10)

        self._asr_engine = QComboBox()
        self._asr_engine.addItems(["none", "vosk", "whisper"])
        self._asr_engine.setCurrentText(config.asr.engine)
        asr_form.addRow("引擎:", self._asr_engine)

        self._asr_model = QLineEdit(config.asr.model_path)
        self._asr_model.setPlaceholderText("模型路径（留空使用默认）")
        asr_form.addRow("模型路径:", self._asr_model)

        layout.addWidget(asr_group)
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
        self._config.asr.engine = self._asr_engine.currentText()
        self._config.asr.model_path = self._asr_model.text()
