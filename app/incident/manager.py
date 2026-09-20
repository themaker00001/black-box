from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Callable

from app.buffer.circular_buffer import CircularBuffer
from app.config.settings import IncidentSettings
from app.events.models import Event, TriggerPayload
from app.incident.models import Incident
from app.incident.snapshot import persist_snapshot

logger = logging.getLogger(__name__)

OnIncidentReady = Callable[[Incident, list[Event]], None]


class IncidentManager:
    """Bridges triggers to evidence processing. When a trigger fires, it grabs
    the pre-incident window from the buffer immediately (so nothing is lost),
    waits briefly for a short post-incident tail, then hands the full snapshot
    off to whatever consumes it next (evidence processor -> agent -> report)."""

    def __init__(
        self,
        buffer: CircularBuffer,
        settings: IncidentSettings,
        pre_incident_seconds: float,
        post_incident_seconds: float,
        on_incident_ready: OnIncidentReady,
    ) -> None:
        self._buffer = buffer
        self._settings = settings
        self._pre_incident_seconds = pre_incident_seconds
        self._post_incident_seconds = post_incident_seconds
        self._on_incident_ready = on_incident_ready
        self._open_incidents = 0
        self._lock = threading.Lock()

    def handle_trigger(self, payload: TriggerPayload) -> None:
        with self._lock:
            if self._open_incidents >= self._settings.max_open_incidents:
                logger.warning(
                    "dropping trigger %s: max_open_incidents (%d) reached",
                    payload.trigger_name,
                    self._settings.max_open_incidents,
                )
                return
            self._open_incidents += 1

        incident = Incident.new(
            trigger_name=payload.trigger_name,
            trigger_reason=payload.reason,
            trigger_details=payload.details,
            base_dir=str(self._settings.output_dir),
        )
        pre_events = self._buffer.snapshot(self._pre_incident_seconds)
        logger.info("incident %s opened: %s (%d pre-trigger events)", incident.incident_id, payload.reason, len(pre_events))

        threading.Thread(
            target=self._finish_incident,
            args=(incident, pre_events),
            name=f"incident-{incident.incident_id}",
            daemon=True,
        ).start()

    def _finish_incident(self, incident: Incident, pre_events: list[Event]) -> None:
        try:
            self._stop_event_wait(self._post_incident_seconds)
            post_events = self._buffer.snapshot()
            merged = self._merge(pre_events, post_events)

            incident.event_count = len(merged)
            events = persist_snapshot(Path(incident.output_dir), merged)
            self._on_incident_ready(incident, events)
        except Exception:
            logger.exception("failed to finalize incident %s", incident.incident_id)
        finally:
            with self._lock:
                self._open_incidents -= 1

    @staticmethod
    def _stop_event_wait(seconds: float) -> None:
        threading.Event().wait(seconds)

    @staticmethod
    def _merge(pre_events: list[Event], post_events: list[Event]) -> list[Event]:
        by_id = {e.event_id: e for e in pre_events}
        for event in post_events:
            by_id[event.event_id] = event
        return sorted(by_id.values(), key=lambda e: e.timestamp)
