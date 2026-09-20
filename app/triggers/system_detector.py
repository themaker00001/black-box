from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable

from app.config.settings import SystemDetectorSettings
from app.events.bus import EventBus
from app.events.models import Event, EventSource, TriggerPayload

OnTrigger = Callable[[TriggerPayload], None]


class SystemDetector:
    """Fires when CPU or memory stays above threshold for `sustained_seconds`.
    Re-arms only after the metric drops back below threshold, so one sustained
    spike produces exactly one incident instead of one per sample."""

    def __init__(self, bus: EventBus, settings: SystemDetectorSettings, on_trigger: OnTrigger) -> None:
        self._settings = settings
        self._on_trigger = on_trigger
        self._breach_started_at: datetime | None = None
        self._armed = True
        if settings.enabled:
            bus.subscribe(self._handle, source=EventSource.SYSTEM)

    def _handle(self, event: Event) -> None:
        if event.event_type != "system.metrics":
            return
        cpu = event.payload.get("cpu_percent", 0.0)
        memory = event.payload.get("memory_percent", 0.0)
        breaching = cpu >= self._settings.cpu_percent_threshold or memory >= self._settings.memory_percent_threshold

        now = event.timestamp
        if not breaching:
            self._breach_started_at = None
            self._armed = True
            return

        if self._breach_started_at is None:
            self._breach_started_at = now

        sustained_for = (now - self._breach_started_at).total_seconds()
        if self._armed and sustained_for >= self._settings.sustained_seconds:
            self._armed = False
            self._on_trigger(
                TriggerPayload(
                    reason=f"CPU/memory sustained above threshold for {sustained_for:.0f}s "
                    f"(cpu={cpu:.1f}%, memory={memory:.1f}%)",
                    trigger_name="system_detector",
                    details={"cpu_percent": cpu, "memory_percent": memory, "sustained_seconds": sustained_for},
                )
            )
