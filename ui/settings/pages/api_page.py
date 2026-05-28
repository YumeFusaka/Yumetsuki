from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QLineEdit,
    QComboBox, QLabel, QGroupBox, QScrollArea, QSlider, QHBoxLayout,
    QPushButton, QFileDialog,
)
from PySide6.QtCore import Qt
from config.schema import APIConfig
from core.model_catalog import STT_MODELS_DIR, is_stt_model_dir, model_path_key, resolve_model_path, scan_model_dirs
from ui.theme import SAKURA_COMBO_BOX_STYLE, settings_page_title
from ui.widgets.removable_combo_box import RemovableComboBox
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
    ASR_DEVICE_OPTIONS = ["cpu", "auto", "cuda"]
    ASR_COMPUTE_TYPE_OPTIONS = ["default", "float16", "int8", "int8_float16"]

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

        title = settings_page_title(QLabel("API 设定"))
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
        self._asr_engine.addItems(["none", "faster_whisper"])
        self._asr_engine.setCurrentText(config.asr.engine)
        asr_form.addRow("引擎:", self._asr_engine)

        self._asr_model_path = RemovableComboBox()
        self._asr_model_path.setEditable(True)
        self._refresh_asr_model_paths()
        self._set_asr_model_path(config.asr.model_path)
        self._asr_model_path.setPlaceholderText("data/models/stt/faster-whisper-large-v3-turbo")
        self._asr_model_path_browse_btn = QPushButton("浏览...")
        self._asr_model_path_browse_btn.setObjectName("browseBtn")
        self._asr_model_path_browse_btn.clicked.connect(self._browse_asr_model_path)
        model_path_layout = QHBoxLayout()
        model_path_layout.setContentsMargins(0, 0, 0, 0)
        model_path_layout.addWidget(self._asr_model_path)
        model_path_layout.addWidget(self._asr_model_path_browse_btn)
        asr_form.addRow("模型目录:", model_path_layout)

        self._asr_device = QComboBox()
        self._asr_device.setEditable(True)
        self._asr_device.addItems(self.ASR_DEVICE_OPTIONS)
        self._asr_device.setCurrentText(config.asr.device)
        self._asr_device.setMinimumWidth(220)
        self._asr_device.setMaximumWidth(220)
        asr_form.addRow("设备:", self._asr_device)

        self._asr_compute_type = QComboBox()
        self._asr_compute_type.setEditable(True)
        self._asr_compute_type.addItems(self.ASR_COMPUTE_TYPE_OPTIONS)
        self._asr_compute_type.setCurrentText(config.asr.compute_type)
        self._asr_compute_type.setMinimumWidth(220)
        self._asr_compute_type.setMaximumWidth(220)
        asr_form.addRow("计算类型:", self._asr_compute_type)

        self._asr_language = QComboBox()
        self._asr_language.setEditable(True)
        self._asr_language.addItems(["auto", *self.TTS_LANGUAGE_OPTIONS])
        self._asr_language.setCurrentText(config.asr.language)
        self._asr_language.setMinimumWidth(220)
        self._asr_language.setMaximumWidth(220)
        asr_form.addRow("语言:", self._asr_language)

        self._asr_transcribe_timeout = RoseSpinBox()
        self._asr_transcribe_timeout.setRange(10, 600)
        self._asr_transcribe_timeout.setValue(config.asr.transcribe_timeout_seconds)
        self._asr_transcribe_timeout.setSuffix(" 秒")
        asr_form.addRow("识别超时:", self._asr_transcribe_timeout)

        self._asr_timeout = RoseSpinBox()
        self._asr_timeout.setRange(3, 120)
        self._asr_timeout.setValue(config.asr.record_timeout_seconds)
        self._asr_timeout.setSuffix(" 秒")
        asr_form.addRow("录音超时:", self._asr_timeout)

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

        self._asr_initial_silence_grace = RoseSpinBox()
        self._asr_initial_silence_grace.setRange(0, 10000)
        self._asr_initial_silence_grace.setValue(config.asr.initial_silence_grace_ms)
        self._asr_initial_silence_grace.setSuffix(" ms")
        asr_form.addRow("起始等待:", self._asr_initial_silence_grace)

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

    def _browse_asr_model_path(self) -> None:
        path = QFileDialog.getExistingDirectory(
            self,
            "选择 faster-whisper 模型目录",
            self._asr_model_path.currentText(),
        )
        if path:
            self._set_asr_model_path(path)

    def _refresh_asr_model_paths(self) -> None:
        self._asr_model_path.clear()
        self._asr_model_path.addItems(scan_model_dirs(STT_MODELS_DIR, is_stt_model_dir))

    def _set_asr_model_path(self, path: str) -> None:
        existing_index = self._find_asr_model_path(path)
        if path and existing_index < 0:
            self._asr_model_path.addItem(path)
            existing_index = self._asr_model_path.count() - 1
        if existing_index >= 0:
            self._asr_model_path.setCurrentIndex(existing_index)
        else:
            self._asr_model_path.setCurrentText(path)
        if self._asr_model_path.lineEdit() is not None:
            self._asr_model_path.lineEdit().setCursorPosition(0)

    def _find_asr_model_path(self, path: str) -> int:
        if not path:
            return -1
        target_key = model_path_key(resolve_model_path(path, STT_MODELS_DIR))
        for index in range(self._asr_model_path.count()):
            item_path = resolve_model_path(self._asr_model_path.itemText(index), STT_MODELS_DIR)
            if model_path_key(item_path) == target_key:
                return index
        return -1

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
        self._config.asr.model_path = self._asr_model_path.currentText().strip()
        self._config.asr.device = self._asr_device.currentText().strip()
        self._config.asr.compute_type = self._asr_compute_type.currentText().strip()
        self._config.asr.language = self._asr_language.currentText().strip()
        self._config.asr.transcribe_timeout_seconds = self._asr_transcribe_timeout.value()
        self._config.asr.record_timeout_seconds = self._asr_timeout.value()
        self._config.asr.silence_threshold = self._asr_silence_threshold.value() / 100.0
        self._config.asr.silence_duration_ms = self._asr_silence_duration.value()
        self._config.asr.initial_silence_grace_ms = self._asr_initial_silence_grace.value()

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
        self._set_asr_model_path(self._config.asr.model_path)
        self._asr_device.setCurrentText(self._config.asr.device)
        self._asr_compute_type.setCurrentText(self._config.asr.compute_type)
        self._asr_language.setCurrentText(self._config.asr.language)
        self._asr_transcribe_timeout.setValue(self._config.asr.transcribe_timeout_seconds)
        self._asr_timeout.setValue(self._config.asr.record_timeout_seconds)
        self._asr_silence_threshold.setValue(int(self._config.asr.silence_threshold * 100))
        self._asr_silence_duration.setValue(self._config.asr.silence_duration_ms)
        self._asr_initial_silence_grace.setValue(self._config.asr.initial_silence_grace_ms)
