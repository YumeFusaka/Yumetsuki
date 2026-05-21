from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QLineEdit,
    QComboBox, QLabel, QGroupBox, QScrollArea, QSlider, QHBoxLayout,
)
from PySide6.QtCore import Qt
from config.schema import APIConfig
from ui.widgets.rose_spin_box import RoseSpinBox

FORM_STYLE = """
QLineEdit, QComboBox {
    background: rgba(255, 255, 255, 0.7);
    border: 1px solid rgba(220, 160, 180, 0.3);
    border-radius: 6px;
    padding: 7px 12px;
    color: #4a3040;
    font-size: 13px;
    min-height: 18px;
}
QLineEdit:focus, QComboBox:focus {
    border-color: #d4567a;
    background: rgba(255, 255, 255, 0.85);
}
QComboBox::drop-down { border: none; padding-right: 8px; }
QComboBox QAbstractItemView {
    background: #fff5f7; border: 1px solid rgba(220, 160, 180, 0.3);
    color: #4a3040; selection-background-color: rgba(255, 154, 162, 0.3);
}
QLabel { color: #6b4a5a; font-size: 13px; }
QGroupBox {
    color: #7a4060; font-size: 14px; font-weight: bold;
    border: 1px solid rgba(220, 160, 180, 0.2);
    border-radius: 10px; margin-top: 10px; padding: 18px 14px 10px 14px;
    background: rgba(255, 255, 255, 0.35);
}
QGroupBox::title { subcontrol-origin: margin; left: 14px; padding: 0 6px; }
QSlider::groove:horizontal {
    height: 4px; background: rgba(220, 160, 180, 0.3); border-radius: 2px;
}
QSlider::handle:horizontal {
    width: 16px; height: 16px; margin: -6px 0;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #ff9aaa, stop:1 #e8a0c8);
    border-radius: 8px;
}
QSlider::sub-page:horizontal {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #ff9aaa, stop:1 #e8a0c8);
    border-radius: 2px;
}
"""


class APIPage(QWidget):
    def __init__(self, config: APIConfig, parent=None):
        super().__init__(parent)
        self._config = config
        self.setStyleSheet(FORM_STYLE)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(32, 20, 32, 20)
        layout.setSpacing(12)

        title = QLabel("API 设定")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: #7a3a5a;")
        layout.addWidget(title)

        # LLM Group
        llm_group = QGroupBox("LLM 大语言模型")
        llm_form = QFormLayout(llm_group)
        llm_form.setSpacing(8)
        llm_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

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

        # Temperature: slider + spinbox
        temp_row = QHBoxLayout()
        self._temp_slider = QSlider(Qt.Orientation.Horizontal)
        self._temp_slider.setRange(0, 200)
        self._temp_slider.setValue(int(config.llm.temperature * 100))
        self._temp_spin = RoseSpinBox()
        self._temp_spin.setRange(0, 200)
        self._temp_spin.setValue(int(config.llm.temperature * 100))
        self._temp_spin.setMinimumWidth(80)
        self._temp_spin.setMaximumWidth(100)
        self._temp_spin.setSuffix("%")
        self._temp_slider.valueChanged.connect(self._temp_spin.setValue)
        self._temp_spin.valueChanged.connect(self._temp_slider.setValue)
        temp_row.addWidget(self._temp_slider)
        temp_row.addWidget(self._temp_spin)
        llm_form.addRow("Temperature:", temp_row)

        # Max tokens: slider + spinbox
        tok_row = QHBoxLayout()
        self._tok_slider = QSlider(Qt.Orientation.Horizontal)
        self._tok_slider.setRange(256, 32768)
        self._tok_slider.setValue(config.llm.max_tokens)
        self._tok_spin = RoseSpinBox()
        self._tok_spin.setRange(256, 32768)
        self._tok_spin.setValue(config.llm.max_tokens)
        self._tok_spin.setMinimumWidth(80)
        self._tok_spin.setMaximumWidth(100)
        self._tok_slider.valueChanged.connect(self._tok_spin.setValue)
        self._tok_spin.valueChanged.connect(self._tok_slider.setValue)
        tok_row.addWidget(self._tok_slider)
        tok_row.addWidget(self._tok_spin)
        llm_form.addRow("Max Tokens:", tok_row)

        layout.addWidget(llm_group)

        # TTS Group
        tts_group = QGroupBox("TTS 语音合成")
        tts_form = QFormLayout(tts_group)
        tts_form.setSpacing(8)
        tts_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

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
        asr_form.setSpacing(8)
        asr_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        self._asr_engine = QComboBox()
        self._asr_engine.addItems(["none", "vosk", "whisper"])
        self._asr_engine.setCurrentText(config.asr.engine)
        asr_form.addRow("引擎:", self._asr_engine)

        self._asr_model = QLineEdit(config.asr.model_path)
        self._asr_model.setPlaceholderText("模型路径（留空使用默认）")
        asr_form.addRow("模型路径:", self._asr_model)

        layout.addWidget(asr_group)
        layout.addStretch()

        scroll.setWidget(container)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

    def apply(self) -> None:
        self._config.llm.provider = self._provider.currentText()
        self._config.llm.model = self._model.text()
        self._config.llm.api_key = self._api_key.text()
        self._config.llm.base_url = self._base_url.text()
        self._config.llm.temperature = self._temp_slider.value() / 100.0
        self._config.llm.max_tokens = self._tok_slider.value()
        self._config.tts.engine = self._tts_engine.currentText()
        self._config.tts.api_url = self._tts_url.text()
        self._config.asr.engine = self._asr_engine.currentText()
        self._config.asr.model_path = self._asr_model.text()

    def reset(self) -> None:
        self._provider.setCurrentText(self._config.llm.provider)
        self._model.setText(self._config.llm.model)
        self._api_key.setText(self._config.llm.api_key)
        self._base_url.setText(self._config.llm.base_url)
        self._temp_slider.setValue(int(self._config.llm.temperature * 100))
        self._temp_spin.setValue(int(self._config.llm.temperature * 100))
        self._tok_slider.setValue(self._config.llm.max_tokens)
        self._tok_spin.setValue(self._config.llm.max_tokens)
        self._tts_engine.setCurrentText(self._config.tts.engine)
        self._tts_url.setText(self._config.tts.api_url)
        self._asr_engine.setCurrentText(self._config.asr.engine)
        self._asr_model.setText(self._config.asr.model_path)
