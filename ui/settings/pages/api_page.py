from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QLineEdit,
    QComboBox, QLabel, QGroupBox, QScrollArea, QSlider, QHBoxLayout,
    QPushButton, QFileDialog,
)
from PySide6.QtCore import Qt
from config.schema import APIConfig
from ui.theme import SAKURA_COMBO_BOX_STYLE
from ui.widgets.rose_spin_box import RoseSpinBox

FORM_STYLE = """
QLineEdit {
    background: rgba(255, 255, 255, 0.7);
    border: 1px solid rgba(220, 160, 180, 0.3);
    border-radius: 6px;
    padding: 7px 12px;
    color: #4a3040;
    font-size: 13px;
    min-height: 18px;
}
QLineEdit:focus {
    border-color: #d4567a;
    background: rgba(255, 255, 255, 0.85);
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
QPushButton#browseBtn {
    background: rgba(255, 255, 255, 0.8);
    border: 1px solid rgba(220, 160, 180, 0.34);
    border-radius: 6px;
    padding: 6px 14px;
    color: #6b4a5a;
    font-size: 13px;
}
QPushButton#browseBtn:hover {
    background: rgba(255, 225, 232, 0.92);
    border-color: rgba(212, 86, 122, 0.44);
}
""" + SAKURA_COMBO_BOX_STYLE


class APIPage(QWidget):
    TTS_LANGUAGE_OPTIONS = ["zh", "ja", "en", "ko", "yue"]
    TTS_AUDIO_MODE_OPTIONS = [
        ("自动（推荐）", "auto"),
        ("PCM流式（低延迟）", "pcm_stream"),
        ("WAV（兼容/调试）", "wav"),
    ]
    TTS_REFERENCE_MODE_OPTIONS = [
        ("自动（推荐）", "auto"),
        ("每次请求携带参考", "inline"),
        ("启动对话时初始化一次", "session_preload"),
        ("参考由服务端管理", "server_managed"),
    ]

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

        self._tts_audio_mode = QComboBox()
        for label, value in self.TTS_AUDIO_MODE_OPTIONS:
            self._tts_audio_mode.addItem(label, value)
        self._set_audio_mode(config.tts.audio_mode)
        self._tts_audio_mode.setToolTip("自动模式优先尝试 PCM 流式，失败后在当前聊天会话回退为 WAV。")
        tts_form.addRow("音频模式:", self._tts_audio_mode)

        ref_audio_row = QWidget()
        ref_audio_layout = QHBoxLayout(ref_audio_row)
        ref_audio_layout.setContentsMargins(0, 0, 0, 0)
        ref_audio_layout.setSpacing(8)

        self._tts_ref_audio = QLineEdit(config.tts.ref_audio_path)
        self._tts_ref_audio.setPlaceholderText("参考音频文件路径（GPT-SoVITS 常需填写）")
        ref_audio_layout.addWidget(self._tts_ref_audio, 1)

        self._tts_ref_audio_browse_btn = QPushButton("浏览...")
        self._tts_ref_audio_browse_btn.setObjectName("browseBtn")
        self._tts_ref_audio_browse_btn.clicked.connect(self._browse_tts_ref_audio)
        ref_audio_layout.addWidget(self._tts_ref_audio_browse_btn)
        tts_form.addRow("参考音频:", ref_audio_row)

        self._tts_reference_mode = QComboBox()
        for label, value in self.TTS_REFERENCE_MODE_OPTIONS:
            self._tts_reference_mode.addItem(label, value)
        self._set_reference_mode(config.tts.reference_mode)
        self._tts_reference_mode.setToolTip("控制参考音频/参考文本是每次携带、会话初始化一次，还是完全由服务端托管。")
        tts_form.addRow("参考模式:", self._tts_reference_mode)

        self._tts_prompt_lang = QComboBox()
        self._tts_prompt_lang.setEditable(True)
        self._tts_prompt_lang.addItems(self.TTS_LANGUAGE_OPTIONS)
        self._tts_prompt_lang.setCurrentText(config.tts.prompt_lang)
        self._tts_prompt_lang.setMaximumWidth(220)
        tts_form.addRow("参考语言:", self._tts_prompt_lang)

        self._tts_output_lang = QComboBox()
        self._tts_output_lang.setEditable(True)
        self._tts_output_lang.addItems(self.TTS_LANGUAGE_OPTIONS)
        self._tts_output_lang.setCurrentText(config.tts.output_lang)
        self._tts_output_lang.setMaximumWidth(220)
        tts_form.addRow("输出语言:", self._tts_output_lang)

        self._tts_prompt_text = QLineEdit(config.tts.prompt_text)
        self._tts_prompt_text.setPlaceholderText("参考音频对应文本")
        tts_form.addRow("参考文本:", self._tts_prompt_text)

        layout.addWidget(tts_group)

        # ASR Group
        asr_group = QGroupBox("ASR 语音识别")
        asr_form = QFormLayout(asr_group)
        asr_form.setSpacing(8)
        asr_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        self._asr_engine = QComboBox()
        self._asr_engine.addItems(["none", "openai_whisper"])
        self._asr_engine.setCurrentText(config.asr.engine)
        asr_form.addRow("引擎:", self._asr_engine)

        self._asr_base_url = QLineEdit(config.asr.base_url)
        self._asr_base_url.setPlaceholderText("OpenAI API Base URL，留空使用官方默认")
        asr_form.addRow("Base URL:", self._asr_base_url)

        self._asr_api_key = QLineEdit(config.asr.api_key)
        self._asr_api_key.setEchoMode(QLineEdit.EchoMode.Password)
        asr_form.addRow("API Key:", self._asr_api_key)

        self._asr_model = QLineEdit(config.asr.model)
        self._asr_model.setPlaceholderText("whisper-1")
        asr_form.addRow("模型:", self._asr_model)

        self._asr_language = QComboBox()
        self._asr_language.setEditable(True)
        self._asr_language.addItems(self.TTS_LANGUAGE_OPTIONS)
        self._asr_language.setCurrentText(config.asr.language)
        self._asr_language.setMaximumWidth(220)
        asr_form.addRow("语言:", self._asr_language)

        self._asr_record_timeout = RoseSpinBox()
        self._asr_record_timeout.setRange(3, 120)
        self._asr_record_timeout.setValue(config.asr.record_timeout_seconds)
        self._asr_record_timeout.setSuffix(" 秒")
        asr_form.addRow("录音超时:", self._asr_record_timeout)

        self._asr_silence_threshold = RoseSpinBox()
        self._asr_silence_threshold.setRange(1, 50)
        self._asr_silence_threshold.setValue(int(config.asr.silence_threshold * 100))
        self._asr_silence_threshold.setSuffix("%")
        asr_form.addRow("静音阈值:", self._asr_silence_threshold)

        self._asr_silence_duration = RoseSpinBox()
        self._asr_silence_duration.setRange(300, 5000)
        self._asr_silence_duration.setValue(config.asr.silence_duration_ms)
        self._asr_silence_duration.setSuffix(" ms")
        asr_form.addRow("静音结束:", self._asr_silence_duration)

        layout.addWidget(asr_group)
        layout.addStretch()

        scroll.setWidget(container)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

    def _browse_tts_ref_audio(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "选择参考音频",
            self._tts_ref_audio.text(),
            "Audio Files (*.wav *.mp3 *.ogg *.flac);;All Files (*)",
        )
        if path:
            self._tts_ref_audio.setText(path)

    def _set_reference_mode(self, reference_mode: str) -> None:
        index = self._tts_reference_mode.findData(reference_mode or "auto")
        if index < 0:
            index = 0
        self._tts_reference_mode.setCurrentIndex(index)

    def _set_audio_mode(self, audio_mode: str) -> None:
        index = self._tts_audio_mode.findData(audio_mode or "auto")
        if index < 0:
            index = 0
        self._tts_audio_mode.setCurrentIndex(index)

    def apply(self) -> None:
        self._config.llm.provider = self._provider.currentText()
        self._config.llm.model = self._model.text()
        self._config.llm.api_key = self._api_key.text()
        self._config.llm.base_url = self._base_url.text()
        self._config.llm.temperature = self._temp_slider.value() / 100.0
        self._config.llm.max_tokens = self._tok_slider.value()
        self._config.tts.engine = self._tts_engine.currentText()
        self._config.tts.api_url = self._tts_url.text()
        self._config.tts.audio_mode = self._tts_audio_mode.currentData()
        self._config.tts.ref_audio_path = self._tts_ref_audio.text()
        self._config.tts.reference_mode = self._tts_reference_mode.currentData()
        self._config.tts.prompt_lang = self._tts_prompt_lang.currentText()
        self._config.tts.output_lang = self._tts_output_lang.currentText()
        self._config.tts.prompt_text = self._tts_prompt_text.text()
        self._config.asr.engine = self._asr_engine.currentText()
        self._config.asr.base_url = self._asr_base_url.text()
        self._config.asr.api_key = self._asr_api_key.text()
        self._config.asr.model = self._asr_model.text()
        self._config.asr.language = self._asr_language.currentText()
        self._config.asr.record_timeout_seconds = self._asr_record_timeout.value()
        self._config.asr.silence_threshold = self._asr_silence_threshold.value() / 100.0
        self._config.asr.silence_duration_ms = self._asr_silence_duration.value()

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
        self._set_audio_mode(self._config.tts.audio_mode)
        self._tts_ref_audio.setText(self._config.tts.ref_audio_path)
        self._set_reference_mode(self._config.tts.reference_mode)
        self._tts_prompt_lang.setCurrentText(self._config.tts.prompt_lang)
        self._tts_output_lang.setCurrentText(self._config.tts.output_lang)
        self._tts_prompt_text.setText(self._config.tts.prompt_text)
        self._asr_engine.setCurrentText(self._config.asr.engine)
        self._asr_base_url.setText(self._config.asr.base_url)
        self._asr_api_key.setText(self._config.asr.api_key)
        self._asr_model.setText(self._config.asr.model)
        self._asr_language.setCurrentText(self._config.asr.language)
        self._asr_record_timeout.setValue(self._config.asr.record_timeout_seconds)
        self._asr_silence_threshold.setValue(int(self._config.asr.silence_threshold * 100))
        self._asr_silence_duration.setValue(self._config.asr.silence_duration_ms)
