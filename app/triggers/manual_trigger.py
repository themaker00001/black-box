from __future__ import annotations

import logging
import threading
from typing import Callable

from app.config.settings import ManualTriggerSettings
from app.events.models import TriggerPayload

logger = logging.getLogger(__name__)

OnTrigger = Callable[[TriggerPayload], None]


class ManualTrigger:
    """Lets a user fire an incident on demand: touch the configured signal file
    (optionally containing a one-line reason) and this poller picks it up.

        echo "app hung, forcing a snapshot" > ~/.blackbox/trigger_now
    """

    def __init__(self, settings: ManualTriggerSettings, on_trigger: OnTrigger) -> None:
        self._settings = settings
        self._on_trigger = on_trigger
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    def start(self) -> None:
        if not self._settings.enabled or self._thread is not None:
            return
        self._settings.signal_file.parent.mkdir(parents=True, exist_ok=True)
        self._thread = threading.Thread(target=self._run, name="manual-trigger", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5)
            self._thread = None

    def _run(self) -> None:
        while not self._stop_event.wait(self._settings.poll_interval_seconds):
            signal_file = self._settings.signal_file
            if not signal_file.exists():
                continue
            reason = self._consume(signal_file)
            self._on_trigger(
                TriggerPayload(
                    reason=reason or "Manual trigger requested by user",
                    trigger_name="manual_trigger",
                    details={},
                )
            )

    def _consume(self, signal_file) -> str:
        try:
            reason = signal_file.read_text().strip()
        except OSError:
            reason = ""
        finally:
            try:
                signal_file.unlink(missing_ok=True)
            except OSError:
                logger.exception("failed to remove manual trigger signal file")
        return reason
