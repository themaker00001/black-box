from __future__ import annotations

import json
import logging
import re
import threading
import time
from datetime import datetime, timezone

from app.config.settings import TerminalCaptureSettings
from app.events.bus import EventBus
from app.events.models import TerminalCommandPayload
from app.events.normalizer import terminal_command_event

logger = logging.getLogger(__name__)

_REDACTED = "[REDACTED]"


class TerminalCollector:
    """Tails a JSONL event log written by a shell hook (scripts/blackbox_zsh_hook.sh).
    Disabled by default: terminal history is sensitive, so this only runs when the
    user explicitly opts in via config, and it never scrapes terminal screen contents."""

    def __init__(self, bus: EventBus, settings: TerminalCaptureSettings) -> None:
        self._bus = bus
        self._settings = settings
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._redact_res = [re.compile(p) for p in settings.redact_patterns]

    def start(self) -> None:
        if not self._settings.enabled:
            logger.info("terminal collector disabled by config; not starting")
            return
        if self._thread is not None:
            return
        self._settings.event_log_path.parent.mkdir(parents=True, exist_ok=True)
        self._settings.event_log_path.touch(exist_ok=True)
        self._thread = threading.Thread(target=self._run, name="terminal-collector", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5)
            self._thread = None

    def _run(self) -> None:
        path = self._settings.event_log_path
        with open(path, "r") as f:
            f.seek(0, 2)  # only new commands from now on, never backfill prior history
            while not self._stop_event.wait(0.5):
                line = f.readline()
                if not line:
                    time.sleep(0.1)
                    continue
                self._handle_line(line)

    def _handle_line(self, line: str) -> None:
        line = line.strip()
        if not line:
            return
        try:
            raw = json.loads(line)
        except json.JSONDecodeError:
            logger.warning("skipping malformed terminal event line")
            return

        command = self._redact(raw.get("command", ""))
        payload = TerminalCommandPayload(
            shell=raw.get("shell", "unknown"),
            command=command,
            exit_code=raw.get("exit_code"),
            stdout=self._maybe_truncate(raw.get("stdout")) if self._settings.capture_stdout else None,
            stderr=self._maybe_truncate(raw.get("stderr")) if self._settings.capture_stderr else None,
            cwd=raw.get("cwd"),
            duration_seconds=raw.get("duration_seconds"),
        )
        self._bus.publish(terminal_command_event(payload))

    def _redact(self, command: str) -> str:
        for pattern in self._redact_res:
            if pattern.search(command):
                return _REDACTED
        return command

    def _maybe_truncate(self, text: str | None) -> str | None:
        if text is None:
            return None
        limit = self._settings.max_output_chars
        return text if len(text) <= limit else text[:limit] + "...[truncated]"
