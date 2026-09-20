from __future__ import annotations

import argparse
import logging
import signal
import threading

from app.agent.debugger import DebugAgent
from app.buffer.circular_buffer import CircularBuffer
from app.capture.os_events import OsEventsCollector
from app.capture.processes import ProcessCollector
from app.capture.screen import ScreenCollector
from app.capture.system import SystemMetricsCollector
from app.capture.terminal import TerminalCollector
from app.config.settings import Settings, load_settings
from app.events.bus import EventBus
from app.events.models import Event
from app.evidence.processor import build_evidence, write_evidence
from app.incident.manager import IncidentManager
from app.incident.models import Incident
from app.llm.ollama import OllamaClient
from app.report.generator import write_report
from app.storage.incident_store import IncidentStore
from app.triggers.crash_detector import CrashDetector
from app.triggers.exception_detector import ExceptionDetector
from app.triggers.manual_trigger import ManualTrigger
from app.triggers.system_detector import SystemDetector
from app.webapp.server import WebServer

logger = logging.getLogger(__name__)


class BlackBox:
    """Wires the whole pipeline together: capture -> bus -> buffer,
    triggers -> incident manager -> evidence -> AI agent -> report/storage."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._bus = EventBus()
        self._screen = ScreenCollector(self._bus, settings.capture.screen)
        self._buffer = CircularBuffer(
            retention_seconds=settings.buffer.retention_seconds,
            on_evict=self._on_evict,
        )
        self._bus.subscribe(self._buffer.add)  # buffer sees every event, regardless of source

        self._collectors = [
            self._screen,
            SystemMetricsCollector(self._bus, settings.capture.system),
            ProcessCollector(self._bus, settings.capture.processes),
            TerminalCollector(self._bus, settings.capture.terminal),
            OsEventsCollector(self._bus, settings.capture.os_events),
        ]

        self._llm = OllamaClient(settings.llm)
        self._agent = DebugAgent(self._llm, settings.llm.model)
        self._store = IncidentStore(settings.storage.database_path)

        self._incident_manager = IncidentManager(
            buffer=self._buffer,
            settings=settings.incident,
            pre_incident_seconds=settings.buffer.pre_incident_seconds,
            post_incident_seconds=settings.buffer.post_incident_seconds,
            on_incident_ready=self._on_incident_ready,
        )

        self._triggers = [
            CrashDetector(self._bus, settings.triggers.crash_detector, self._incident_manager.handle_trigger),
            ExceptionDetector(self._bus, settings.triggers.exception_detector, self._incident_manager.handle_trigger),
            SystemDetector(self._bus, settings.triggers.system_detector, self._incident_manager.handle_trigger),
        ]
        self._manual_trigger = ManualTrigger(settings.triggers.manual_trigger, self._incident_manager.handle_trigger)
        self._web_server = WebServer(self._buffer, self._store, settings)

    def _on_evict(self, event: Event) -> None:
        if event.event_type == "screen.capture":
            self._screen.delete_image(event.payload.get("image_path", ""))

    def _on_incident_ready(self, incident: Incident, events: list[Event]) -> None:
        logger.info("processing incident %s (%d events)", incident.incident_id, len(events))
        evidence = build_evidence(incident, events)
        write_evidence(incident, evidence)
        analysis = self._agent.investigate(evidence)
        report_path = write_report(incident, evidence, analysis)
        self._store.save(incident, analysis, str(report_path))
        logger.info("incident %s report written to %s", incident.incident_id, report_path)

    def start(self) -> None:
        logger.info("starting Black Box (retention=%.0fs)", self._settings.buffer.retention_seconds)
        for collector in self._collectors:
            collector.start()
        self._manual_trigger.start()
        self._web_server.start()

    def stop(self) -> None:
        logger.info("stopping Black Box")
        self._web_server.stop()
        self._manual_trigger.stop()
        for collector in self._collectors:
            collector.stop()

    def run_forever(self) -> None:
        self.start()
        stop_event = threading.Event()
        signal.signal(signal.SIGINT, lambda *_: stop_event.set())
        signal.signal(signal.SIGTERM, lambda *_: stop_event.set())
        try:
            stop_event.wait()
        finally:
            self.stop()


def _configure_logging(level: str) -> None:
    logging.basicConfig(level=level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


def main() -> None:
    parser = argparse.ArgumentParser(prog="blackbox", description="Local privacy-first computer black box")
    parser.add_argument("--config", default=None, help="Path to config.yaml")
    parser.add_argument(
        "command",
        nargs="?",
        default="run",
        choices=["run"],
        help="run: start capturing and watch for incidents (default)",
    )
    args = parser.parse_args()

    settings = load_settings(args.config)
    _configure_logging(settings.logging.level)

    black_box = BlackBox(settings)
    if args.command == "run":
        black_box.run_forever()


if __name__ == "__main__":
    main()
