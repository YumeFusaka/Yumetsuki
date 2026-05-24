from collections import defaultdict
from threading import RLock
from typing import Any, Callable


class EventBus:
    def __init__(self):
        self._handlers: dict[str, list[Callable]] = defaultdict(list)
        self._lock = RLock()

    def subscribe(self, event: str, handler: Callable) -> None:
        with self._lock:
            self._handlers[event].append(handler)

    def unsubscribe(self, event: str, handler: Callable) -> None:
        with self._lock:
            handlers = self._handlers[event]
            if handler in handlers:
                handlers.remove(handler)

    def publish(self, event: str, data: Any = None) -> None:
        with self._lock:
            handlers = list(self._handlers[event])
        for handler in handlers:
            handler(data)


event_bus = EventBus()
