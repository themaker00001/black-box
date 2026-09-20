from app.events.bus import EventBus
from app.events.models import Event, EventSource


def test_wildcard_subscriber_sees_every_event():
    bus = EventBus()
    seen = []
    bus.subscribe(seen.append)

    bus.publish(Event(source=EventSource.SYSTEM, event_type="system.metrics", payload={}))
    bus.publish(Event(source=EventSource.PROCESS, event_type="process.snapshot", payload={}))

    assert len(seen) == 2


def test_source_scoped_subscriber_only_sees_that_source():
    bus = EventBus()
    system_events = []
    bus.subscribe(system_events.append, source=EventSource.SYSTEM)

    bus.publish(Event(source=EventSource.SYSTEM, event_type="system.metrics", payload={}))
    bus.publish(Event(source=EventSource.PROCESS, event_type="process.snapshot", payload={}))

    assert len(system_events) == 1
    assert system_events[0].source == EventSource.SYSTEM


def test_subscriber_exception_does_not_break_other_subscribers():
    bus = EventBus()
    seen = []

    def broken(_event):
        raise RuntimeError("boom")

    bus.subscribe(broken)
    bus.subscribe(seen.append)
    bus.publish(Event(source=EventSource.SYSTEM, event_type="system.metrics", payload={}))

    assert len(seen) == 1
