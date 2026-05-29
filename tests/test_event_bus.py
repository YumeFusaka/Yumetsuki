from core.event_bus import EventBus
from python_core.rpc.context import RpcContext
from python_core.rpc.event_bus_shim import EventBusShim
from python_core.rpc.event_publisher import RpcEventPublisher


class _HeadlessEventBus:
    def __init__(self):
        self._handlers = {}

    def subscribe(self, event, handler):
        self._handlers.setdefault(event, []).append(handler)

        def unsubscribe():
            self._handlers[event].remove(handler)

        return unsubscribe

    def publish(self, event, data):
        for handler in list(self._handlers.get(event, [])):
            handler(data)


def _context(payload):
    return RpcContext(
        request_id=payload["request_id"],
        trace_id=payload["trace_id"],
        parent_trace_id=None,
        session_id=payload["session_id"],
        deadline_ms=30000,
    )


def test_event_bus_publish_uses_snapshot_of_handlers():
    bus = EventBus()
    seen = []

    def first(data):
        seen.append(("first", data))
        bus.unsubscribe("x", first)

    def second(data):
        seen.append(("second", data))

    bus.subscribe("x", first)
    bus.subscribe("x", second)

    bus.publish("x", 1)

    assert seen == [("first", 1), ("second", 1)]


def test_event_bus_shim_projects_headless_events_to_rpc_publisher():
    bus = _HeadlessEventBus()
    publisher = RpcEventPublisher()
    shim = EventBusShim(publisher, _context)

    shim.attach(bus, "legacy.log", "logs.batch")
    bus.publish(
        "legacy.log",
        {
            "request_id": "req_logs",
            "trace_id": "trace_logs",
            "session_id": "sess_logs",
            "entries": ["a", "b"],
        },
    )

    events = publisher.drain()
    assert [event["type"] for event in events] == ["logs.batch"]
    assert events[0]["request_id"] == "req_logs"
    assert events[0]["payload"]["entries"] == ["a", "b"]

    shim.close()
    bus.publish(
        "legacy.log",
        {
            "request_id": "req_ignored",
            "trace_id": "trace_logs",
            "session_id": "sess_logs",
            "entries": ["ignored"],
        },
    )
    assert publisher.drain() == []
