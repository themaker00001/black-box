from __future__ import annotations

import logging
import threading
import time
from pathlib import Path

import mss
from PIL import Image

from app.config.settings import ScreenCaptureSettings
from app.events.bus import EventBus
from app.events.models import ScreenCapturePayload
from app.events.normalizer import screen_capture_event

logger = logging.getLogger(__name__)


class ScreenCollector:
    """Periodic screenshots via mss. Has no concept of retention or incidents —
    it just produces timestamped screen observations and saves them to disk,
    referencing the file path in the event payload."""

    def __init__(self, bus: EventBus, settings: ScreenCaptureSettings) -> None:
        self._bus = bus
        self._settings = settings
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._settings.storage_dir.mkdir(parents=True, exist_ok=True)

    def start(self) -> None:
        if self._thread is not None:
            return
        self._thread = threading.Thread(target=self._run, name="screen-collector", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5)
            self._thread = None

    def _run(self) -> None:
        with mss.mss() as sct:
            monitors = self._select_monitors(sct)
            while not self._stop_event.wait(self._settings.interval_seconds):
                for monitor_id, monitor in monitors:
                    try:
                        self._capture_one(sct, monitor_id, monitor)
                    except Exception:
                        logger.exception("screen capture failed for monitor %s", monitor_id)

    def _select_monitors(self, sct: mss.mss) -> list[tuple[int, dict]]:
        all_monitors = sct.monitors  # index 0 is the virtual "all monitors" bounding box
        if self._settings.monitor == "all":
            return list(enumerate(all_monitors))[1:] or [(0, all_monitors[0])]
        index = int(self._settings.monitor)
        return [(index, all_monitors[index])]

    def _capture_one(self, sct: mss.mss, monitor_id: int, monitor: dict) -> None:
        grab = sct.grab(monitor)
        image = Image.frombytes("RGB", grab.size, grab.bgra, "raw", "BGRX")
        image = self._downscale(image)

        timestamp_ns = time.time_ns()
        filename = f"{timestamp_ns}_m{monitor_id}.png"
        path = self._settings.storage_dir / filename
        image.save(path, format="PNG", optimize=True)

        payload = ScreenCapturePayload(
            monitor_id=monitor_id,
            image_path=str(path),
            width=image.width,
            height=image.height,
        )
        self._bus.publish(screen_capture_event(payload))

    def _downscale(self, image: Image.Image) -> Image.Image:
        max_dim = self._settings.max_dimension
        if max(image.width, image.height) <= max_dim:
            return image
        scale = max_dim / max(image.width, image.height)
        new_size = (int(image.width * scale), int(image.height * scale))
        return image.resize(new_size, Image.BILINEAR)

    def delete_image(self, image_path: str) -> None:
        """Called by the buffer's eviction hook so screenshots don't outlive their event."""
        try:
            Path(image_path).unlink(missing_ok=True)
        except Exception:
            logger.exception("failed to delete evicted screenshot %s", image_path)
