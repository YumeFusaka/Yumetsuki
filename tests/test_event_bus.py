from core.event_bus import EventBus


def test_subscribe_and_publish():
    bus = EventBus()
    received = []
    bus.subscribe("test", lambda data: received.append(data))
    bus.publish("test", {"msg": "hello"})
    assert received == [{"msg": "hello"}]


def test_unsubscribe():
    bus = EventBus()
    received = []
    handler = lambda data: received.append(data)
    bus.subscribe("test", handler)
    bus.unsubscribe("test", handler)
    bus.publish("test", {"msg": "hello"})
    assert received == []


def test_multiple_subscribers():
    bus = EventBus()
    results = []
    bus.subscribe("evt", lambda d: results.append("a"))
    bus.subscribe("evt", lambda d: results.append("b"))
    bus.publish("evt", None)
    assert results == ["a", "b"]
