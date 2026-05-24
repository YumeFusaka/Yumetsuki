from core.event_bus import EventBus


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
