from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QLineEdit,
    QCheckBox, QComboBox, QLabel, QGroupBox, QScrollArea, QSizePolicy,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QFontDatabase
from config.schema import SystemConfig
from ui.theme import SettingsFontTokens, font_for_role, sakura_combo_box_style, settings_font_tokens, settings_page_title
from ui.widgets.rose_spin_box import RoseSpinBox

def system_page_style(system_config_or_tokens: SystemConfig | SettingsFontTokens | None = None) -> str:
    tokens = (
        system_config_or_tokens
        if isinstance(system_config_or_tokens, SettingsFontTokens)
        else settings_font_tokens(system_config_or_tokens)
    )
    return f"""
QLineEdit {{
    background: rgba(255, 255, 255, 0.7);
    border: 1px solid rgba(220, 160, 180, 0.3);
    border-radius: 6px; padding: 8px 12px;
    color: #4a3040; font-size: {tokens.body}px;
    min-height: 20px; min-width: 280px;
}}
QLineEdit:focus {{
    border-color: #d4567a;
    background: rgba(255, 255, 255, 0.85);
}}
QLabel {{ color: #6b4a5a; font-size: {tokens.body}px; }}
QGroupBox {{
    color: #7a4060; font-size: {tokens.section}px; font-weight: bold;
    border: 1px solid rgba(220, 160, 180, 0.2);
    border-radius: 10px; margin-top: 12px; padding-top: 14px;
    background: rgba(255, 255, 255, 0.35);
}}
QGroupBox::title {{ subcontrol-origin: margin; left: 16px; padding: 0 6px; }}
QCheckBox {{
    color: #6b4a5a;
    font-size: {tokens.body}px;
    spacing: 8px;
}}
QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border-radius: 5px;
    border: 1px solid rgba(212, 86, 122, 0.45);
    background: rgba(255, 255, 255, 0.76);
}}
QCheckBox::indicator:checked {{
    background: #d4567a;
    border-color: #d4567a;
}}
""" + sakura_combo_box_style(tokens.body)


FORM_STYLE = system_page_style()


def _settings_font_token_key(system_config_or_tokens: SystemConfig | SettingsFontTokens | None) -> tuple:
    tokens = (
        system_config_or_tokens
        if isinstance(system_config_or_tokens, SettingsFontTokens)
        else settings_font_tokens(system_config_or_tokens)
    )
    return (
        tokens.family,
        tokens.raw,
        tokens.base,
        tokens.small,
        tokens.body,
        tokens.list,
        tokens.button,
        tokens.section,
        tokens.title,
        tokens.mono,
        tokens.html_small,
        tokens.html_body,
    )


def _font_families(current_font: str) -> list[str]:
    try:
        families = list(QFontDatabase.families())
    except Exception:
        families = []
    if current_font and current_font not in families:
        families.insert(0, current_font)
    if "Microsoft YaHei" not in families:
        families.append("Microsoft YaHei")
    return list(dict.fromkeys(families))


class SystemPage(QWidget):
    def __init__(self, config: SystemConfig, parent=None):
        super().__init__(parent)
        self._config = config
        self.setStyleSheet(system_page_style(config))

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(32, 22, 32, 22)
        layout.setSpacing(14)

        self._title = settings_page_title(QLabel("系统设置"))
        layout.addWidget(self._title)

        appearance = QGroupBox("基础外观")
        app_form = QFormLayout(appearance)
        self._configure_form(app_form)

        self._language = QComboBox()
        self._language.addItem("简体中文（当前仅支持）", "zh-CN")
        self._language.setCurrentIndex(0)
        self._language.setEnabled(False)
        self._language.setToolTip("当前仅支持简体中文")
        self._prepare_field(self._language)
        app_form.addRow("语言:", self._language)

        self._theme = QComboBox()
        self._theme.addItem("Sakura", "sakura")
        self._theme.setCurrentIndex(0)
        self._prepare_field(self._theme)
        app_form.addRow("主题:", self._theme)

        self._font = QComboBox()
        self._font.setEditable(True)
        self._font_default_font = self._font.font()
        self._populate_font_combo(_font_families(config.font_family))
        self._font.setCurrentText(config.font_family)
        self._prepare_field(self._font)
        app_form.addRow("字体:", self._font)

        self._font_size = RoseSpinBox()
        self._font_size.setRange(10, 24)
        self._font_size.setValue(config.font_size)
        self._prepare_field(self._font_size)
        app_form.addRow("字号:", self._font_size)

        layout.addWidget(appearance)

        self._display_group = QGroupBox("聊天显示")
        display_form = QFormLayout(self._display_group)
        self._configure_form(display_form)

        self._chat_font_scale = RoseSpinBox()
        self._chat_font_scale.setRange(50, 200)
        self._chat_font_scale.setValue(int(config.chat_display.font_scale * 100))
        self._chat_font_scale.setSuffix("%")
        self._prepare_field(self._chat_font_scale)
        display_form.addRow("聊天字号倍率:", self._chat_font_scale)

        layout.addWidget(self._display_group)

        self._passive_group = QGroupBox("被动状态")
        passive_form = QFormLayout(self._passive_group)
        self._configure_form(passive_form)

        self._idle_threshold = RoseSpinBox()
        self._idle_threshold.setRange(1, 120)
        self._idle_threshold.setValue(max(1, round(config.passive_interaction.idle_threshold_seconds / 60)))
        self._idle_threshold.setSuffix(" 分钟")
        self._prepare_field(self._idle_threshold)
        passive_form.addRow("空闲阈值:", self._idle_threshold)

        layout.addWidget(self._passive_group)

        self._bubble_group = QGroupBox("被动气泡")
        bubble_form = QFormLayout(self._bubble_group)
        self._configure_form(bubble_form)

        self._bubble_scale = RoseSpinBox()
        self._bubble_scale.setRange(50, 200)
        self._bubble_scale.setValue(int(config.chat_display.bubble_scale * 100))
        self._bubble_scale.setSuffix("%")
        self._prepare_field(self._bubble_scale)
        bubble_form.addRow("气泡缩放:", self._bubble_scale)

        self._bubble_max_width = RoseSpinBox()
        self._bubble_max_width.setRange(120, 800)
        self._bubble_max_width.setValue(config.passive_interaction.bubble_max_width)
        self._bubble_max_width.setSuffix(" px")
        self._prepare_field(self._bubble_max_width)
        bubble_form.addRow("气泡最大宽度:", self._bubble_max_width)

        self._bubble_duration = RoseSpinBox()
        self._bubble_duration.setRange(1, 60)
        self._bubble_duration.setValue(config.passive_interaction.bubble_duration_seconds)
        self._bubble_duration.setSuffix(" 秒")
        self._prepare_field(self._bubble_duration)
        bubble_form.addRow("气泡停留时长:", self._bubble_duration)

        layout.addWidget(self._bubble_group)

        self._vision_group = QGroupBox("视觉 / OCR")
        vision_form = QFormLayout(self._vision_group)
        self._configure_form(vision_form)

        self._vision_enabled = QCheckBox("启用屏幕 OCR")
        self._vision_enabled.setChecked(config.vision.enabled)
        self._vision_enabled.setToolTip("启用后，用户显式要求读屏时才会采集屏幕文字。")
        vision_form.addRow("OCR:", self._vision_enabled)

        self._ocr_engine = QComboBox()
        self._ocr_engine.addItem("RapidOCR（默认）", "rapidocr")
        self._ocr_engine.addItem("PaddleOCR（进阶，可选安装）", "paddleocr")
        self._ocr_engine.setCurrentIndex(max(0, self._ocr_engine.findData(config.vision.ocr_engine)))
        self._prepare_field(self._ocr_engine)
        vision_form.addRow("识别后端:", self._ocr_engine)

        self._ocr_language = QComboBox()
        self._ocr_language.setEditable(True)
        for language in ("ch", "en", "japan", "korean", "chinese_cht"):
            self._ocr_language.addItem(language)
        self._ocr_language.setCurrentText(config.vision.language)
        self._prepare_field(self._ocr_language)
        vision_form.addRow("语言:", self._ocr_language)

        self._vision_max_text = RoseSpinBox()
        self._vision_max_text.setRange(200, 10000)
        self._vision_max_text.setValue(config.vision.max_text_chars)
        self._vision_max_text.setSuffix(" 字")
        self._prepare_field(self._vision_max_text)
        vision_form.addRow("读屏文字上限:", self._vision_max_text)

        self._vision_screenshot_dir = QLineEdit(config.vision.screenshot_dir)
        self._vision_screenshot_dir.setPlaceholderText("data/vision")
        self._prepare_field(self._vision_screenshot_dir)
        vision_form.addRow("截图目录:", self._vision_screenshot_dir)

        self._vision_retention_hours = RoseSpinBox()
        self._vision_retention_hours.setRange(1, 720)
        self._vision_retention_hours.setValue(config.vision.screenshot_retention_hours)
        self._vision_retention_hours.setSuffix(" 小时")
        self._prepare_field(self._vision_retention_hours)
        vision_form.addRow("截图保留:", self._vision_retention_hours)

        self._vision_max_files = RoseSpinBox()
        self._vision_max_files.setRange(10, 10000)
        self._vision_max_files.setValue(config.vision.screenshot_max_files)
        self._vision_max_files.setSuffix(" 张")
        self._prepare_field(self._vision_max_files)
        vision_form.addRow("最多截图:", self._vision_max_files)

        self._vision_cleanup_interval = RoseSpinBox()
        self._vision_cleanup_interval.setRange(1, 1440)
        self._vision_cleanup_interval.setValue(config.vision.screenshot_cleanup_interval_minutes)
        self._vision_cleanup_interval.setSuffix(" 分钟")
        self._prepare_field(self._vision_cleanup_interval)
        vision_form.addRow("清理间隔:", self._vision_cleanup_interval)

        self._passive_vision_enabled = QCheckBox("被动状态定时读屏")
        self._passive_vision_enabled.setChecked(config.vision.passive_observation_enabled)
        self._passive_vision_enabled.setToolTip("进入被动状态后按间隔自动读取屏幕，仅在用户显式开启时生效。")
        vision_form.addRow("被动定时:", self._passive_vision_enabled)

        self._passive_vision_interval = RoseSpinBox()
        self._passive_vision_interval.setRange(3, 300)
        self._passive_vision_interval.setValue(config.vision.passive_observation_interval_seconds)
        self._passive_vision_interval.setSuffix(" 秒")
        self._prepare_field(self._passive_vision_interval)
        vision_form.addRow("读屏间隔:", self._passive_vision_interval)
        self._passive_vision_interval.setEnabled(config.vision.passive_observation_enabled)
        self._passive_vision_enabled.toggled.connect(self._passive_vision_interval.setEnabled)
        self._passive_vision_enabled.toggled.connect(lambda checked: self._vision_enabled.setChecked(True) if checked else None)

        self._vision_explicit_only = QCheckBox("固定仅显式读屏触发")
        self._vision_explicit_only.setChecked(True)
        self._vision_explicit_only.setEnabled(False)
        self._vision_explicit_only.setToolTip("当前版本固定只允许显式读屏触发，避免后台自动采集屏幕。")
        vision_form.addRow("触发方式:", self._vision_explicit_only)

        layout.addWidget(self._vision_group)

        # Network
        network = QGroupBox("网络")
        net_form = QFormLayout(network)
        self._configure_form(net_form)

        self._proxy = QLineEdit(config.proxy)
        self._proxy.setPlaceholderText("http://127.0.0.1:7890（留空不使用代理）")
        self._prepare_field(self._proxy)
        net_form.addRow("HTTP 代理:", self._proxy)

        layout.addWidget(network)
        layout.addStretch()

        scroll.setWidget(container)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)
        self.apply_settings_font_tree(settings_font_tokens(config))

    def apply_settings_font_tree(self, tokens: SettingsFontTokens) -> bool:
        token_key = _settings_font_token_key(tokens)
        if self.property("_settingsFontTreeTokenKey") == token_key:
            return True
        self.setStyleSheet(system_page_style(tokens))
        self._title.setFont(font_for_role(tokens, "title"))
        self._title.setStyleSheet(
            f"font-weight: bold; color: #7a3a5a; font-size: {tokens.title}px;"
        )
        for spin_box in (
            self._font_size,
            self._chat_font_scale,
            self._idle_threshold,
            self._bubble_scale,
            self._bubble_max_width,
            self._bubble_duration,
            self._vision_max_text,
            self._passive_vision_interval,
        ):
            spin_box.apply_settings_tokens(tokens)
        self.setProperty("_settingsFontTreeTokenKey", token_key)
        self.setProperty("_settingsFontTokenKey", token_key)
        return True

    @staticmethod
    def _configure_form(form: QFormLayout) -> None:
        form.setContentsMargins(30, 26, 30, 20)
        form.setHorizontalSpacing(18)
        form.setVerticalSpacing(12)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.DontWrapRows)

    @staticmethod
    def _prepare_field(widget: QWidget) -> None:
        widget.setMinimumWidth(280)
        widget.setMinimumHeight(36)
        widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def _populate_font_combo(self, families: list[str]) -> None:
        for family in families:
            self._font.addItem(family)
            index = self._font.count() - 1
            if self._can_preview_font(family):
                self._font.setItemData(index, QFont(family), Qt.ItemDataRole.FontRole)

    def _apply_font_preview(self, family: str) -> None:
        if family and self._can_preview_font(family):
            self._font.setFont(QFont(family))
        else:
            self._font.setFont(self._font_default_font)

    @staticmethod
    def _can_preview_font(family: str) -> bool:
        if not family:
            return False
        try:
            return bool(QFontDatabase.isSmoothlyScalable(family))
        except Exception:
            return False

    def apply(self) -> None:
        self._config.language = self._language.currentData() or "zh-CN"
        self._config.theme = self._theme.currentData() or "sakura"
        self._config.font_family = self._font.currentText().strip()
        self._config.font_size = self._font_size.value()
        self._config.chat_display.font_scale = self._chat_font_scale.value() / 100.0
        self._config.chat_display.bubble_scale = self._bubble_scale.value() / 100.0
        self._config.passive_interaction.idle_threshold_seconds = self._idle_threshold.value() * 60
        self._config.passive_interaction.bubble_max_width = self._bubble_max_width.value()
        self._config.passive_interaction.bubble_duration_seconds = self._bubble_duration.value()
        self._config.vision.enabled = self._vision_enabled.isChecked() or self._passive_vision_enabled.isChecked()
        self._config.vision.ocr_engine = self._ocr_engine.currentData() or "rapidocr"
        self._config.vision.language = self._ocr_language.currentText().strip() or "ch"
        self._config.vision.max_text_chars = self._vision_max_text.value()
        self._config.vision.screenshot_dir = self._vision_screenshot_dir.text().strip() or "data/vision"
        self._config.vision.screenshot_retention_hours = self._vision_retention_hours.value()
        self._config.vision.screenshot_max_files = self._vision_max_files.value()
        self._config.vision.screenshot_cleanup_interval_minutes = self._vision_cleanup_interval.value()
        self._config.vision.passive_observation_enabled = self._passive_vision_enabled.isChecked()
        self._config.vision.passive_observation_interval_seconds = self._passive_vision_interval.value()
        self._config.vision.explicit_trigger_only = True
        self._config.proxy = self._proxy.text()

    def reset(self) -> None:
        self._language.setCurrentIndex(0)
        self._theme.setCurrentIndex(0)
        self._font.setCurrentText(self._config.font_family)
        self._font_size.setValue(self._config.font_size)
        self._chat_font_scale.setValue(int(self._config.chat_display.font_scale * 100))
        self._bubble_scale.setValue(int(self._config.chat_display.bubble_scale * 100))
        self._idle_threshold.setValue(max(1, round(self._config.passive_interaction.idle_threshold_seconds / 60)))
        self._bubble_max_width.setValue(self._config.passive_interaction.bubble_max_width)
        self._bubble_duration.setValue(self._config.passive_interaction.bubble_duration_seconds)
        self._vision_enabled.setChecked(self._config.vision.enabled)
        self._ocr_engine.setCurrentIndex(max(0, self._ocr_engine.findData(self._config.vision.ocr_engine)))
        self._ocr_language.setCurrentText(self._config.vision.language)
        self._vision_max_text.setValue(self._config.vision.max_text_chars)
        self._vision_screenshot_dir.setText(self._config.vision.screenshot_dir)
        self._vision_retention_hours.setValue(self._config.vision.screenshot_retention_hours)
        self._vision_max_files.setValue(self._config.vision.screenshot_max_files)
        self._vision_cleanup_interval.setValue(self._config.vision.screenshot_cleanup_interval_minutes)
        self._passive_vision_enabled.setChecked(self._config.vision.passive_observation_enabled)
        self._passive_vision_interval.setValue(self._config.vision.passive_observation_interval_seconds)
        self._passive_vision_interval.setEnabled(self._passive_vision_enabled.isChecked())
        self._vision_explicit_only.setChecked(True)
        self._proxy.setText(self._config.proxy)
