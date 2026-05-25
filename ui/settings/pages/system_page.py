from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QLineEdit,
    QComboBox, QLabel, QGroupBox, QScrollArea, QSizePolicy,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QFontDatabase
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
QGroupBox {
    color: #7a4060; font-size: 15px; font-weight: bold;
    border: 1px solid rgba(220, 160, 180, 0.2);
    border-radius: 10px; margin-top: 12px; padding-top: 14px;
    background: rgba(255, 255, 255, 0.35);
}
QGroupBox::title { subcontrol-origin: margin; left: 16px; padding: 0 6px; }
""" + SAKURA_COMBO_BOX_STYLE


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
        self.setStyleSheet(FORM_STYLE)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(32, 22, 32, 22)
        layout.setSpacing(14)

        title = QLabel("系统设置")
        title.setStyleSheet("font-size: 22px; font-weight: bold; color: #7a3a5a;")
        layout.addWidget(title)

        appearance = QGroupBox("基础外观")
        app_form = QFormLayout(appearance)
        self._configure_form(app_form)

        self._language = QComboBox()
        self._language.addItems(["zh-CN", "en-US", "ja-JP"])
        self._language.setCurrentText(config.language)
        self._prepare_field(self._language)
        app_form.addRow("语言:", self._language)

        self._theme = QComboBox()
        self._theme.addItems(["sakura"])
        self._theme.setCurrentText("sakura")
        self._prepare_field(self._theme)
        app_form.addRow("主题:", self._theme)

        self._font = QComboBox()
        self._font.setEditable(True)
        self._font_default_font = self._font.font()
        self._populate_font_combo(_font_families(config.font_family))
        self._font.setCurrentText(config.font_family)
        self._apply_font_preview(config.font_family)
        self._font.currentTextChanged.connect(self._apply_font_preview)
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
        self._config.language = self._language.currentText()
        self._config.theme = self._theme.currentText()
        self._config.font_family = self._font.currentText().strip()
        self._config.font_size = self._font_size.value()
        self._config.chat_display.font_scale = self._chat_font_scale.value() / 100.0
        self._config.chat_display.bubble_scale = self._bubble_scale.value() / 100.0
        self._config.passive_interaction.idle_threshold_seconds = self._idle_threshold.value() * 60
        self._config.passive_interaction.bubble_max_width = self._bubble_max_width.value()
        self._config.passive_interaction.bubble_duration_seconds = self._bubble_duration.value()
        self._config.proxy = self._proxy.text()
