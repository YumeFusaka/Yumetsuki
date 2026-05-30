from PySide6.QtCore import QEvent, QPoint, Qt
from PySide6.QtWidgets import QLabel, QProgressBar, QVBoxLayout, QWidget


class StartupLoadingWindow(QWidget):
    def __init__(self):
        super().__init__(None, Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFixedSize(420, 210)
        self._drag_offset: QPoint | None = None

        shell = QWidget(self)
        shell.setObjectName("startup-shell")
        shell.setGeometry(0, 0, 420, 210)
        shell.installEventFilter(self)

        layout = QVBoxLayout(shell)
        layout.setContentsMargins(34, 28, 34, 28)
        layout.setSpacing(14)

        title = QLabel("Yumetsuki")
        title.setObjectName("startup-title")
        title.installEventFilter(self)
        layout.addWidget(title)

        subtitle = QLabel("设置中心正在准备")
        subtitle.setObjectName("startup-subtitle")
        subtitle.installEventFilter(self)
        layout.addWidget(subtitle)

        layout.addStretch(1)

        self._message = QLabel("准备启动...")
        self._message.setObjectName("startup-message")
        self._message.installEventFilter(self)
        layout.addWidget(self._message)

        self._progress = QProgressBar()
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        self._progress.setTextVisible(False)
        self._progress.installEventFilter(self)
        layout.addWidget(self._progress)

        self.setStyleSheet("""
            QWidget#startup-shell {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #fffafd, stop:0.48 #fff0f5, stop:1 #f9e6f4);
                border: 1px solid rgba(220, 150, 178, 0.38);
                border-radius: 18px;
            }
            QLabel#startup-title {
                color: #8f2f5a;
                font-size: 28px;
                font-weight: 700;
            }
            QLabel#startup-subtitle {
                color: #7a5263;
                font-size: 13px;
            }
            QLabel#startup-message {
                color: #5c3848;
                font-size: 13px;
            }
            QProgressBar {
                background: rgba(255, 255, 255, 0.72);
                border: 1px solid rgba(220, 150, 178, 0.28);
                border-radius: 7px;
                height: 12px;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #ff9aaa, stop:0.55 #e8a0c8, stop:1 #c8a0e8);
                border-radius: 6px;
            }
        """)

    def update_progress(self, message: str, value: int) -> None:
        self._message.setText(message)
        self._progress.setValue(value)

    def eventFilter(self, watched, event):
        if event.type() == QEvent.Type.MouseButtonPress and self._handle_drag_press(event):
            return True
        if event.type() == QEvent.Type.MouseMove and self._handle_drag_move(event):
            return True
        if event.type() == QEvent.Type.MouseButtonRelease and self._handle_drag_release(event):
            return True
        return super().eventFilter(watched, event)

    def mousePressEvent(self, event) -> None:
        if self._handle_drag_press(event):
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._handle_drag_move(event):
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if self._handle_drag_release(event):
            return
        super().mouseReleaseEvent(event)

    def _handle_drag_press(self, event) -> bool:
        if event.button() != Qt.MouseButton.LeftButton:
            return False
        self._drag_offset = event.globalPosition().toPoint() - self.pos()
        event.accept()
        return True

    def _handle_drag_move(self, event) -> bool:
        if self._drag_offset is None or not event.buttons() & Qt.MouseButton.LeftButton:
            return False
        self.move(event.globalPosition().toPoint() - self._drag_offset)
        event.accept()
        return True

    def _handle_drag_release(self, event) -> bool:
        if event.button() != Qt.MouseButton.LeftButton:
            return False
        self._drag_offset = None
        event.accept()
        return True
