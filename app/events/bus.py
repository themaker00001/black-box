from __future__ import annotations

import logging
import threading
from collections import defaultdict
from typing import Callable

from app.events.models import Event, EventSource

logger = logging.getLogger(__name__)

Subscriber = Callable[[Event], None]

_WILDCARD = "*"


class EventBus:
    """Minimal in-process pub/sub. Collectors publish; the buffer and triggers subscribe."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._subscribers: dict[str, list[Subscriber]] = defaultdict(list)

    def subscribe(self, callback: Subscriber, source: EventSource | str | None = None) -> None:
        key = _WILDCARD if source is None else str(source.value if isinstance(source, EventSource) else source)
        with self._lock:
            self._subscribers[key].append(callback)

    def publish(self, event: Event) -> None:
        with self._lock:
            callbacks = list(self._subscribers.get(_WILDCARD, [])) + list(
                self._subscribers.get(event.source.value, [])
            )
        for callback in callbacks:
            try:
                callback(event)
            except Exception:
                logger.exception("event subscriber raised while handling %s", event.event_type)
