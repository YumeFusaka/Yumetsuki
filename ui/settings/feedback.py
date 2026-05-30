from __future__ import annotations

from typing import cast

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, QRect, Qt, QTimer
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from ui.text_metrics import clamped_text_width
from ui.theme import apply_settings_fonts, set_settings_font_role


class ConfirmDialog(QDialog):
    def __init__(self, title: str, message: str, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMinimumWidth(380)
        self.setStyleSheet("""
            QLabel#titleLabel {
                color: #7a3a5a;
                font-size: 16px;
                font-weight: 700;
                background: transparent;
            }
            QLabel#bodyLabel {
                color: #5f4754;
                font-size: 13px;
                background: transparent;
            }
            QPushButton {
                background: rgba(255, 255, 255, 0.8);
                border: 1px solid rgba(220, 160, 180, 0.34);
                border-radius: 8px;
                padding: 8px 18px;
                color: #6b4a5a;
                font-size: 13px;
            }
            QPushButton:hover {
                background: rgba(255, 225, 232, 0.92);
                border-color: rgba(212, 86, 122, 0.44);
            }
        """)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(14, 14, 14, 14)
        outer.setSpacing(0)

        card = QFrame()
        card.setObjectName("confirmCard")
        card.setStyleSheet("""
            QFrame#confirmCard {
                background: rgba(255, 248, 251, 0.98);
                border: 1px solid rgba(220, 160, 180, 0.24);
                border-radius: 16px;
            }
        """)
        outer.addWidget(card)

        shadow = QGraphicsDropShadowEffect(card)
        shadow.setBlurRadius(26)
        shadow.setOffset(0, 8)
        shadow.setColor(QColor(161, 103, 128, 60))
        card.setGraphicsEffect(shadow)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(14)

        title_label = QLabel(title)
        title_label.setObjectName("titleLabel")
        set_settings_font_role(title_label, "title")
        layout.addWidget(title_label)

        body_label = QLabel(message)
        body_label.setObjectName("bodyLabel")
        set_settings_font_role(body_label, "body")
        body_label.setWordWrap(True)
        layout.addWidget(body_label)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Yes | QDialogButtonBox.StandardButton.No
        )
        yes_button = buttons.button(QDialogButtonBox.StandardButton.Yes)
        no_button = buttons.button(QDialogButtonBox.StandardButton.No)
        yes_button.setText("确认")
        no_button.setText("取消")
        yes_button.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #ff9aaa, stop:1 #e8a0c8);
                color: white;
                border: none;
                border-radius: 8px;
                padding: 8px 20px;
                font-weight: 700;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #ffb0be, stop:1 #f0b0d8);
            }
        """)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        apply_settings_fonts(self, _system_config(parent))


class ToastMessage(QFrame):
    MAX_WIDTH = 700
    MIN_WIDTH = 220
    MARGIN = 14
    GAP = 8
    OUTER_MARGIN_X = 8
    CARD_MARGIN_X = 14
    DOT_WIDTH = 8
    BODY_SPACING = 10

    def __init__(self, message: str, success: bool, host: QWidget):
        super().__init__(host)
        self._host = host
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.ToolTip)

        accent = "#67b36b" if success else "#e06a7d"
        self.setStyleSheet(f"""
            QFrame#toastCard {{
                background: rgba(255, 251, 253, 0.96);
                border: 1px solid rgba(220, 160, 180, 0.18);
                border-radius: 14px;
            }}
            QLabel#bodyLabel {{
                color: #6b4a5a;
                font-size: 12px;
                background: transparent;
            }}
        """)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(self.OUTER_MARGIN_X, 8, self.OUTER_MARGIN_X, 8)
        outer.setSpacing(0)

        card = QFrame()
        card.setObjectName("toastCard")
        outer.addWidget(card)

        shadow = QGraphicsDropShadowEffect(card)
        shadow.setBlurRadius(20)
        shadow.setOffset(0, 6)
        shadow.setColor(QColor(161, 103, 128, 42))
        card.setGraphicsEffect(shadow)

        layout = QHBoxLayout(card)
        layout.setContentsMargins(self.CARD_MARGIN_X, 10, self.CARD_MARGIN_X, 10)
        layout.setSpacing(self.BODY_SPACING)

        dot = QFrame()
        dot.setFixedSize(8, 8)
        dot.setStyleSheet(f"background: {accent}; border-radius: 4px;")
        layout.addWidget(dot, alignment=Qt.AlignmentFlag.AlignVCenter)

        body_label = QLabel(message)
        body_label.setObjectName("bodyLabel")
        set_settings_font_role(body_label, "small")
        body_label.setWordWrap(True)
        layout.addWidget(body_label, 1)
        apply_settings_fonts(self, _system_config(host))

        chrome_width = self._chrome_width()
        max_width = self._available_max_width(host)
        width = clamped_text_width(
            body_label,
            message,
            min_width=min(self.MIN_WIDTH, max_width),
            max_width=max_width,
            chrome_width=chrome_width,
        )
        body_width = max(1, width - chrome_width)
        body_label.setMinimumWidth(body_width)
        body_label.setMaximumWidth(body_width)
        self.setFixedSize(width, self.sizeHint().height())

    @classmethod
    def _chrome_width(cls) -> int:
        return cls.OUTER_MARGIN_X * 2 + cls.CARD_MARGIN_X * 2 + cls.DOT_WIDTH + cls.BODY_SPACING

    @classmethod
    def _available_max_width(cls, host: QWidget) -> int:
        host_width = host.width() if host is not None else cls.MAX_WIDTH
        return max(1, min(cls.MAX_WIDTH, host_width - cls.MARGIN * 2))

    def show_toast(self) -> None:
        toasts = _toast_list(self._host)
        toasts.append(self)
        _reposition_toasts(self._host)
        self.show()
        self.raise_()

        start = self.geometry()
        start.moveLeft(start.x() + 16)
        self.setGeometry(start)
        end = self.geometry()
        end.moveLeft(end.x() - 16)
        anim = QPropertyAnimation(self, b"geometry")
        anim.setDuration(170)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.setStartValue(start)
        anim.setEndValue(end)
        self._anim = anim
        anim.start()

        QTimer.singleShot(2200, self.close)

    def closeEvent(self, event) -> None:
        super().closeEvent(event)
        toasts = _toast_list(self._host)
        if self in toasts:
            toasts.remove(self)
            _reposition_toasts(self._host)


def confirm_action(parent: QWidget, title: str, message: str) -> bool:
    dlg = ConfirmDialog(title, message, parent)
    return dlg.exec() == QDialog.DialogCode.Accepted


def show_feedback(parent: QWidget, title: str, message: str, *, success: bool = True) -> None:
    host = parent.window() if parent is not None else parent
    host = cast(QWidget, host)
    toast = ToastMessage(message or title, success, host)
    toast.show_toast()


def _toast_list(host: QWidget) -> list[ToastMessage]:
    toasts = host.property("_yumetsuki_toasts")
    if toasts is None:
        toasts = []
        host.setProperty("_yumetsuki_toasts", toasts)
    return cast(list[ToastMessage], toasts)


def _system_config(parent: QWidget | None):
    while parent is not None:
        config = getattr(parent, "_config", None)
        if config is not None and hasattr(config, "system"):
            return config.system
        parent = parent.parent()
    return None


def _reposition_toasts(host: QWidget) -> None:
    toasts = _toast_list(host)
    widest = max((toast.width() for toast in toasts), default=ToastMessage.MAX_WIDTH)
    left = max(ToastMessage.MARGIN, (host.width() - widest) // 2)
    top = ToastMessage.MARGIN
    for index, toast in enumerate(toasts):
        toast_height = toast.height()
        y = top + sum(
            prev.height() + ToastMessage.GAP
            for prev in toasts[:index]
        )
        toast.setGeometry(QRect(left, y, toast.width(), toast_height))
