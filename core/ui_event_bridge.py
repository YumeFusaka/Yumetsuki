from __future__ import annotations

from collections import deque

from PySide6.QtCore import QObject, QThread, QTimer, Qt, Signal


class UIEventBridge(QObject):
    ui_event_ready = Signal(str, object)
    log_batch_ready = Signal(object)
    _log_enqueue_requested = Signal(str)

    def __init__(
        self,
        log_max_buffer: int,
        log_flush_interval_ms: int,
        ui_dispatch_throttle_ms: int,
        parent=None,
    ):
        super().__init__(parent)
        self._ui_dispatch_throttle_ms = ui_dispatch_throttle_ms
        self._log_buffer = deque(maxlen=log_max_buffer)
        self._log_enqueue_requested.connect(
            self._enqueue_log_on_ui_thread,
            Qt.ConnectionType.QueuedConnection,
        )
        self._log_timer = QTimer(self)
        self._log_timer.setSingleShot(True)
        self._log_timer.setInterval(log_flush_interval_ms)
        self._log_timer.timeout.connect(self.flush_logs)

    def dispatch_ui_event(self, event_name: str, payload: object) -> None:
        self.ui_event_ready.emit(event_name, payload)

    def enqueue_log(self, text: str) -> None:
        if QThread.currentThread() == self.thread():
            self._enqueue_log_on_ui_thread(text)
            return
        self._log_enqueue_requested.emit(text)

    def _enqueue_log_on_ui_thread(self, text: str) -> None:
        self._log_buffer.append(text)
        if not self._log_timer.isActive():
            self._log_timer.start()

    def flush_logs(self) -> None:
        if not self._log_buffer:
            return
        batch = list(self._log_buffer)
        self._log_buffer.clear()
        self.log_batch_ready.emit(batch)
