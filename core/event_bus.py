from collections import defaultdict
from typing import Any, Callable


class EventBus:
    def __init__(self):
        self._handlers: dict[str, list[Callable]] = defaultdict(list)

    def subscribe(self, event: str, handler: Callable) -> None:
        self._handlers[event].append(handler)

    def unsubscribe(self, event: str, handler: Callable) -> None:
        self._handlers[event].remove(handler)

    def publish(self, event: str, data: Any = None) -> None:
        for handler in self._handlers[event]:
            handler(data)


event_bus = EventBus()
