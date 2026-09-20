from __future__ import annotations

from typing import Callable

from app.config.settings import CrashDetectorSettings
from app.events.bus import EventBus
from app.events.models import Event, EventSource
from app.events.models import TriggerPayload

OnTrigger = Callable[[TriggerPayload], None]


class CrashDetector:
    """Fires the moment the OS-events collector reports a crash report file.
    Purely reactive: no thread of its own, it just subscribes to the bus."""

    def __init__(self, bus: EventBus, settings: CrashDetectorSettings, on_trigger: OnTrigger) -> None:
        self._settings = settings
        self._on_trigger = on_trigger
        if settings.enabled:
            bus.subscribe(self._handle, source=EventSource.OS_EVENT)

    def _handle(self, event: Event) -> None:
        if event.event_type != "os.crash_report":
            return
        process_name = event.payload.get("process_name") or "unknown process"
        self._on_trigger(
            TriggerPayload(
                reason=f"Crash report generated for {process_name}",
                trigger_name="crash_detector",
                details=event.payload,
            )
        )
