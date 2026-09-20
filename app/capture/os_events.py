from __future__ import annotations

import logging
import re
import subprocess
import threading
from datetime import datetime, timezone
from pathlib import Path

from app.config.settings import OsEventsCaptureSettings
from app.events.bus import EventBus
from app.events.models import OsEventPayload
from app.events.normalizer import os_event

logger = logging.getLogger(__name__)

_CRASH_NAME_RE = re.compile(r"^(?P<name>.+?)_\d{4}-\d{2}-\d{2}-\d{6}")
_SIGNAL_RE = re.compile(r"Signal:\s*(SIG\w+)", re.IGNORECASE)
_TERMINATION_RE = re.compile(r"Termination Reason:\s*(.+)", re.IGNORECASE)
_EXCEPTION_TYPE_RE = re.compile(r"Exception Type:\s*(.+)", re.IGNORECASE)
_PID_RE = re.compile(r'"pid"\s*:\s*(\d+)')


class OsEventsCollector:
    """macOS-native failure signals: crash reporter files under DiagnosticReports
    and crash-related entries from the unified log. Kept separate from screen/system
    capture so this module's only job is 'did the OS report something going wrong'."""

    def __init__(self, bus: EventBus, settings: OsEventsCaptureSettings) -> None:
        self._bus = bus
        self._settings = settings
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._seen_reports: set[str] = set()
        self._log_watermark = datetime.now(timezone.utc)

    def start(self) -> None:
        if self._thread is not None:
            return
        self._seed_known_reports()
        self._thread = threading.Thread(target=self._run, name="os-events-collector", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5)
            self._thread = None

    def _seed_known_reports(self) -> None:
        # Don't replay crash reports that predate this run.
        directory = self._settings.diagnostic_reports_dir
        if directory.exists():
            self._seen_reports = {p.name for p in directory.iterdir() if p.is_file()}

    def _run(self) -> None:
        while not self._stop_event.wait(self._settings.poll_interval_seconds):
            self._poll_crash_reports()
            self._poll_unified_log()

    def _poll_crash_reports(self) -> None:
        directory = self._settings.diagnostic_reports_dir
        if not directory.exists():
            return
        try:
            files = [p for p in directory.iterdir() if p.is_file()]
        except OSError:
            return

        for path in files:
            if path.name in self._seen_reports:
                continue
            self._seen_reports.add(path.name)
            self._emit_crash_report(path)

    def _emit_crash_report(self, path: Path) -> None:
        match = _CRASH_NAME_RE.match(path.name)
        process_name = match.group("name") if match else path.stem

        try:
            text = path.read_text(errors="ignore")[:20000]
        except OSError:
            text = ""

        signal_match = _SIGNAL_RE.search(text)
        reason_match = _TERMINATION_RE.search(text) or _EXCEPTION_TYPE_RE.search(text)
        pid_match = _PID_RE.search(text)

        message = reason_match.group(1).strip() if reason_match else f"Crash report generated for {process_name}"

        self._bus.publish(
            os_event(
                OsEventPayload(
                    category="crash_report",
                    process_name=process_name,
                    pid=int(pid_match.group(1)) if pid_match else None,
                    signal=signal_match.group(1) if signal_match else None,
                    message=message,
                    raw_source=str(path),
                )
            )
        )

    def _poll_unified_log(self) -> None:
        if not self._settings.unified_log_predicate:
            return
        start = self._log_watermark
        self._log_watermark = datetime.now(timezone.utc)
        start_str = start.astimezone().strftime("%Y-%m-%d %H:%M:%S")

        try:
            result = subprocess.run(
                [
                    "log", "show",
                    "--style", "ndjson",
                    "--start", start_str,
                    "--predicate", self._settings.unified_log_predicate,
                ],
                capture_output=True,
                text=True,
                timeout=max(self._settings.poll_interval_seconds * 2, 5),
            )
        except Exception:
            logger.exception("failed to query unified log")
            return

        if result.returncode != 0 or not result.stdout:
            return

        import json

        for line in result.stdout.splitlines():
            line = line.strip()
            if not line or not line.startswith("{"):
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            self._bus.publish(
                os_event(
                    OsEventPayload(
                        category="unified_log",
                        process_name=record.get("processImagePath", "").rsplit("/", 1)[-1] or None,
                        pid=record.get("processID"),
                        message=record.get("eventMessage", ""),
                        raw_source="unified_log",
                    )
                )
            )
