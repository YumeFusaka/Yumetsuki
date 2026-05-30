from __future__ import annotations

from typing import Any, Callable

from .context import RpcContext
from .event_publisher import RpcEventPublisher


class EventBusShim:
    def __init__(self, event_bus: Any, publisher: RpcEventPublisher, context_factory: Callable[[dict[str, Any]], RpcContext | None]) -> None:
        self.event_bus = event_bus
        self.publisher = publisher
        self.context_factory = context_factory
        self._listener = None

    def start(self) -> None:
        def listener(event: dict[str, Any]) -> None:
            context = self.context_factory(event)
            if context is None:
                return
            self.publisher.publish(context, event["type"], event.get("payload", {}))

        self._listener = listener
        self.event_bus.subscribe(listener)

    def stop(self) -> None:
        if self._listener is not None:
            self.event_bus.unsubscribe(self._listener)
            self._listener = None
