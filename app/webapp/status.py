from __future__ import annotations

from datetime import datetime, timezone

from app.buffer.circular_buffer import CircularBuffer
from app.config.settings import SystemDetectorSettings


def build_status(buffer: CircularBuffer, thresholds: SystemDetectorSettings, recent_incidents: list) -> dict:
    """Pure function (no Flask/DB coupling) so the 'is everything OK' logic is
    unit-testable on its own: latest metrics/processes from the buffer, plus
    whether an incident fired recently or a threshold is currently breached."""
    events = buffer.snapshot(seconds=15)
    latest_metrics = _latest(events, "system.metrics")
    latest_processes = _latest(events, "process.snapshot")

    breaching = False
    if latest_metrics:
        breaching = (
            latest_metrics.payload.get("cpu_percent", 0) >= thresholds.cpu_percent_threshold
            or latest_metrics.payload.get("memory_percent", 0) >= thresholds.memory_percent_threshold
        )

    recent_incident = _most_recent_within(recent_incidents, seconds=300)

    return {
        "ok": not breaching and recent_incident is None,
        "cpu_percent": latest_metrics.payload.get("cpu_percent") if latest_metrics else None,
        "memory_percent": latest_metrics.payload.get("memory_percent") if latest_metrics else None,
        "net_sent_bytes_per_sec": latest_metrics.payload.get("net_sent_bytes_per_sec") if latest_metrics else None,
        "net_recv_bytes_per_sec": latest_metrics.payload.get("net_recv_bytes_per_sec") if latest_metrics else None,
        "top_processes": (latest_processes.payload.get("processes", [])[:8] if latest_processes else []),
        "buffered_events": len(events),
        "most_recent_incident_id": recent_incident,
    }


def _latest(events: list, event_type: str):
    matches = [e for e in events if e.event_type == event_type]
    return max(matches, key=lambda e: e.timestamp) if matches else None


def _most_recent_within(rows: list, seconds: float) -> str | None:
    now = datetime.now(timezone.utc)
    for row in rows:
        created_at = row["created_at"] if not isinstance(row["created_at"], str) else datetime.fromisoformat(row["created_at"])
        if (now - created_at).total_seconds() <= seconds:
            return row["incident_id"]
    return None
