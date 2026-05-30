from core.event_bus import EventBus
from core.ui_event_bridge import UIEventBridge


def _app():
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    return app or QApplication([])


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


def test_ui_event_bridge_flushes_log_batch_in_order():
    _app()
    bridge = UIEventBridge(log_max_buffer=4, log_flush_interval_ms=10, ui_dispatch_throttle_ms=0)
    received = []
    bridge.log_batch_ready.connect(lambda batch: received.extend(batch))

    bridge.enqueue_log("a")
    bridge.enqueue_log("b")
    bridge.flush_logs()

    assert received == ["a", "b"]
