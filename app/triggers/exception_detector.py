from __future__ import annotations

import re
from typing import Callable

from app.config.settings import ExceptionDetectorSettings
from app.events.bus import EventBus
from app.events.models import Event, EventSource, TriggerPayload

OnTrigger = Callable[[TriggerPayload], None]

_EXCEPTION_KEYWORDS_RE = re.compile(
    r"\b(exception|fatal error|panic|unhandled|traceback|segmentation fault|abort trap)\b",
    re.IGNORECASE,
)


class ExceptionDetector:
    """Catches failures that don't produce a crash report: unified-log entries
    mentioning an exception/panic, and terminal commands that exit non-zero
    with a traceback in their output (when terminal output capture is on)."""

    def __init__(self, bus: EventBus, settings: ExceptionDetectorSettings, on_trigger: OnTrigger) -> None:
        self._settings = settings
        self._on_trigger = on_trigger
        if settings.enabled:
            bus.subscribe(self._handle_os_event, source=EventSource.OS_EVENT)
            bus.subscribe(self._handle_terminal_event, source=EventSource.TERMINAL)

    def _handle_os_event(self, event: Event) -> None:
        if event.event_type != "os.unified_log":
            return
        message = event.payload.get("message", "")
        if _EXCEPTION_KEYWORDS_RE.search(message):
            self._on_trigger(
                TriggerPayload(
                    reason=f"Unified log reported: {message[:200]}",
                    trigger_name="exception_detector",
                    details=event.payload,
                )
            )

    def _handle_terminal_event(self, event: Event) -> None:
        if event.event_type != "terminal.command":
            return
        exit_code = event.payload.get("exit_code")
        stderr = event.payload.get("stderr") or ""
        if exit_code and exit_code != 0 and _EXCEPTION_KEYWORDS_RE.search(stderr):
            self._on_trigger(
                TriggerPayload(
                    reason=f"Command exited {exit_code} with an unhandled exception: "
                    f"{event.payload.get('command', '')[:120]}",
                    trigger_name="exception_detector",
                    details=event.payload,
                )
            )
