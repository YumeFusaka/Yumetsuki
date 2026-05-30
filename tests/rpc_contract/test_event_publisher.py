from __future__ import annotations

import importlib.util

import pytest

from python_core.rpc.context import RpcContext
from python_core.rpc.event_bus_shim import EventBusShim
from python_core.rpc.event_publisher import RpcEventPublisher
from python_core.rpc.tasks import TaskRegistry


class FakeEventBus:
    def __init__(self) -> None:
        self.listeners = []

    def subscribe(self, listener) -> None:
        self.listeners.append(listener)

    def unsubscribe(self, listener) -> None:
        self.listeners.remove(listener)

    def emit(self, event: dict) -> None:
        for listener in list(self.listeners):
            listener(event)


def context() -> RpcContext:
    return RpcContext("req_evt", "trace", None, "sess", 1)


def test_context_is_required_and_sequence_increments() -> None:
    registry = TaskRegistry()
    registry.accept_long_task("req_evt", "chat")
    publisher = RpcEventPublisher(registry)
    with pytest.raises(ValueError, match="RpcContext"):
        publisher.publish(None, "chat.delta", {})
    first = publisher.publish(context(), "chat.delta", {"text": "a"})
    second = publisher.publish(context(), "chat.delta", {"text": "b"})
    assert (first.sequence, second.sequence) == (1, 2)


def test_duplicate_terminal_is_rejected_by_task_registry() -> None:
    registry = TaskRegistry()
    registry.accept_long_task("req_evt", "chat")
    publisher = RpcEventPublisher(registry)
    publisher.terminal(context(), "done", "ok")
    with pytest.raises(ValueError, match="duplicate_terminal"):
        publisher.terminal(context(), "done", "again")


def test_event_bus_shim_converts_and_unsubscribes() -> None:
    registry = TaskRegistry()
    registry.accept_long_task("req_evt", "chat")
    publisher = RpcEventPublisher(registry)
    bus = FakeEventBus()
    shim = EventBusShim(bus, publisher, lambda _: context())
    shim.start()
    bus.emit({"type": "chat.delta", "payload": {"text": "hello"}})
    assert publisher.events[-1].type == "chat.delta"
    shim.stop()
    assert bus.listeners == []


def test_ui_event_bridge_not_imported_in_sidecar_path() -> None:
    assert importlib.util.find_spec("python_core.rpc.event_bus_shim") is not None
    assert "core.ui_event_bridge" not in EventBusShim.__module__
