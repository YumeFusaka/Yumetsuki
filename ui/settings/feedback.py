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
        layout.addWidget(title_label)

        body_label = QLabel(message)
        body_label.setObjectName("bodyLabel")
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


class ToastMessage(QFrame):
    MAX_WIDTH = 320
    MARGIN = 14
    GAP = 8

    def __init__(self, message: str, success: bool, host: QWidget):
        super().__init__(host)
        self._host = host
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.ToolTip)
        self.setMinimumWidth(220)
        self.setMaximumWidth(self.MAX_WIDTH)

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
        outer.setContentsMargins(8, 8, 8, 8)
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
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(10)

        dot = QFrame()
        dot.setFixedSize(8, 8)
        dot.setStyleSheet(f"background: {accent}; border-radius: 4px;")
        layout.addWidget(dot, alignment=Qt.AlignmentFlag.AlignVCenter)

        body_label = QLabel(message)
        body_label.setObjectName("bodyLabel")
        body_label.setWordWrap(True)
        body_label.setMaximumWidth(self.MAX_WIDTH - 54)
        layout.addWidget(body_label, 1)
        self.setFixedSize(self.sizeHint())

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
