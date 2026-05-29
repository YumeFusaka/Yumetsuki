from __future__ import annotations

from collections import deque
from threading import RLock, Timer
from typing import Callable


class LocalEvent:
    def __init__(self) -> None:
        self._handlers: list[Callable[..., None]] = []
        self._lock = RLock()

    def connect(self, handler: Callable[..., None], *args, **kwargs) -> Callable[..., None]:
        with self._lock:
            if handler not in self._handlers:
                self._handlers.append(handler)
        return handler

    def disconnect(self, handler: Callable[..., None]) -> None:
        with self._lock:
            self._handlers = [item for item in self._handlers if item is not handler]

    def emit(self, *args, **kwargs) -> None:
        with self._lock:
            handlers = list(self._handlers)
        for handler in handlers:
            handler(*args, **kwargs)


class UIEventBridge:
    """Headless event bridge kept for legacy callers during the Tauri migration."""

    def __init__(
        self,
        log_max_buffer: int,
        log_flush_interval_ms: int,
        ui_dispatch_throttle_ms: int,
        parent=None,
    ):
        self.ui_event_ready = LocalEvent()
        self.log_batch_ready = LocalEvent()
        self._log_enqueue_requested = LocalEvent()
        self._ui_dispatch_throttle_ms = ui_dispatch_throttle_ms
        self._log_buffer = deque(maxlen=log_max_buffer)
        self._log_flush_interval_seconds = max(0, log_flush_interval_ms) / 1000
        self._log_timer: Timer | None = None
        self._lock = RLock()
        self._log_enqueue_requested.connect(self._enqueue_log_on_ui_thread)

    def dispatch_ui_event(self, event_name: str, payload: object) -> None:
        self.ui_event_ready.emit(event_name, payload)

    def enqueue_log(self, text: str) -> None:
        self._log_enqueue_requested.emit(text)

    def _enqueue_log_on_ui_thread(self, text: str) -> None:
        with self._lock:
            self._log_buffer.append(text)
            if self._log_flush_interval_seconds <= 0:
                should_flush = True
            else:
                should_flush = False
                if self._log_timer is None or not self._log_timer.is_alive():
                    self._log_timer = Timer(self._log_flush_interval_seconds, self.flush_logs)
                    self._log_timer.daemon = True
                    self._log_timer.start()
        if should_flush:
            self.flush_logs()

    def flush_logs(self) -> None:
        with self._lock:
            if self._log_timer is not None:
                self._log_timer.cancel()
                self._log_timer = None
            if not self._log_buffer:
                return
            batch = list(self._log_buffer)
            self._log_buffer.clear()
        self.log_batch_ready.emit(batch)

    def close(self) -> None:
        with self._lock:
            timer = self._log_timer
            self._log_timer = None
        if timer is not None:
            timer.cancel()
        self.flush_logs()
