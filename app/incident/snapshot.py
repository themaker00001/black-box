from __future__ import annotations

import json
import logging
import shutil
from pathlib import Path

from app.events.models import Event

logger = logging.getLogger(__name__)


def persist_snapshot(incident_dir: Path, events: list[Event]) -> list[Event]:
    """Writes the raw event snapshot to disk and copies any referenced screenshots
    into the incident directory, since the circular buffer will delete the
    originals once they age out — the incident must own durable copies."""
    incident_dir.mkdir(parents=True, exist_ok=True)
    screenshots_dir = incident_dir / "screenshots"

    rewritten: list[Event] = []
    for event in events:
        if event.event_type == "screen.capture":
            event = _copy_screenshot(event, screenshots_dir)
        rewritten.append(event)

    raw_path = incident_dir / "raw_events.json"
    with open(raw_path, "w") as f:
        json.dump([json.loads(e.model_dump_json()) for e in rewritten], f, indent=2, default=str)

    return rewritten


def _copy_screenshot(event: Event, screenshots_dir: Path) -> Event:
    source = Path(event.payload.get("image_path", ""))
    if not source.exists():
        return event
    screenshots_dir.mkdir(parents=True, exist_ok=True)
    destination = screenshots_dir / source.name
    try:
        shutil.copy2(source, destination)
    except OSError:
        logger.exception("failed to copy screenshot %s into incident snapshot", source)
        return event

    updated = event.model_copy(deep=True)
    updated.payload["image_path"] = str(destination)
    return updated


def load_snapshot(incident_dir: Path) -> list[Event]:
    raw_path = incident_dir / "raw_events.json"
    if not raw_path.exists():
        return []
    with open(raw_path, "r") as f:
        raw = json.load(f)
    return [Event.model_validate(item) for item in raw]
