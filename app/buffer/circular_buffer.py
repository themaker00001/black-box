from __future__ import annotations

import logging
import threading
from collections import deque
from datetime import datetime, timezone
from typing import Callable

from app.events.models import Event

logger = logging.getLogger(__name__)

EvictionCallback = Callable[[Event], None]


class CircularBuffer:
    """Time-windowed store of Events. Knows nothing about incidents or triggers —
    it just keeps the last `retention_seconds` of events and evicts older ones."""

    def __init__(self, retention_seconds: float, on_evict: EvictionCallback | None = None) -> None:
        self._retention_seconds = retention_seconds
        self._events: deque[Event] = deque()
        self._lock = threading.Lock()
        self._on_evict = on_evict

    def add(self, event: Event) -> None:
        with self._lock:
            self._events.append(event)
            self._evict_locked()

    def _evict_locked(self) -> None:
        cutoff = datetime.now(timezone.utc)
        while self._events and self._events[0].age_seconds(cutoff) > self._retention_seconds:
            expired = self._events.popleft()
            if self._on_evict:
                try:
                    self._on_evict(expired)
                except Exception:
                    logger.exception("eviction callback failed for event %s", expired.event_id)

    def snapshot(self, seconds: float | None = None) -> list[Event]:
        """Return a chronological copy of buffered events, optionally limited to
        the trailing `seconds` window (used when an incident wants less than the full buffer)."""
        with self._lock:
            self._evict_locked()
            events = list(self._events)
        if seconds is None:
            return events
        cutoff = datetime.now(timezone.utc)
        return [e for e in events if e.age_seconds(cutoff) <= seconds]

    def __len__(self) -> int:
        with self._lock:
            return len(self._events)
