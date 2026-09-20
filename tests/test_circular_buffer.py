from datetime import datetime, timedelta, timezone

from app.buffer.circular_buffer import CircularBuffer
from app.events.models import Event, EventSource


def _event_at(seconds_ago: float) -> Event:
    return Event(
        source=EventSource.SYSTEM,
        event_type="system.metrics",
        payload={},
        timestamp=datetime.now(timezone.utc) - timedelta(seconds=seconds_ago),
    )


def test_snapshot_preserves_insertion_order():
    # The buffer is an append-only deque, not a sorted structure — collectors
    # publish roughly in real-time order, so insertion order is what matters.
    buf = CircularBuffer(retention_seconds=300)
    first = _event_at(10)
    second = _event_at(5)
    third = _event_at(1)
    buf.add(first)
    buf.add(second)
    buf.add(third)

    snapshot = buf.snapshot()
    assert [e.event_id for e in snapshot] == [first.event_id, second.event_id, third.event_id]


def test_events_older_than_retention_are_evicted():
    buf = CircularBuffer(retention_seconds=5)
    buf.add(_event_at(10))  # already stale
    buf.add(_event_at(1))

    assert len(buf) == 1


def test_eviction_callback_is_invoked_for_expired_events():
    evicted = []
    buf = CircularBuffer(retention_seconds=5, on_evict=evicted.append)
    stale = _event_at(10)
    buf.add(stale)
    buf.add(_event_at(1))  # triggers eviction check on the next add

    assert stale in evicted


def test_snapshot_seconds_limits_to_trailing_window():
    buf = CircularBuffer(retention_seconds=300)
    buf.add(_event_at(200))
    buf.add(_event_at(10))

    recent_only = buf.snapshot(seconds=30)
    assert len(recent_only) == 1
