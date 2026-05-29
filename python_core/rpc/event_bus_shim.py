from __future__ import annotations

from typing import Any, Callable

from .context import RpcContext
from .event_publisher import RpcEventPublisher


class EventBusShim:
    def __init__(self, publisher: RpcEventPublisher, context_factory: Callable[[dict[str, Any]], RpcContext]) -> None:
        self._publisher = publisher
        self._context_factory = context_factory
        self._unsubscribers: list[Callable[[], None]] = []
        self._closed = False

    def attach(self, event_bus: Any, source_event: str, target_event: str) -> None:
        if self._closed:
            raise RuntimeError("event bus shim is closed")

        def listener(payload: dict[str, Any]) -> None:
            if self._closed:
                return
            self._publisher.publish(target_event, self._context_factory(payload), payload)

        unsubscribe = event_bus.subscribe(source_event, listener)
        self._unsubscribers.append(unsubscribe)

    def close(self) -> None:
        self._closed = True
        for unsubscribe in self._unsubscribers:
            unsubscribe()
        self._unsubscribers.clear()
