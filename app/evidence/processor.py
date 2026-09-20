from __future__ import annotations

from collections import Counter

from pydantic import BaseModel

from app.events.models import Event
from app.evidence.correlation import CorrelationFinding, correlate
from app.evidence.timeline import TimelineEntry, build_timeline
from app.incident.models import Incident


class EvidencePackage(BaseModel):
    incident_id: str
    trigger_name: str
    trigger_reason: str
    event_counts_by_source: dict[str, int]
    timeline: list[dict]
    correlations: list[CorrelationFinding]
    representative_screenshot: str | None = None


def build_evidence(incident: Incident, events: list[Event]) -> EvidencePackage:
    timeline_entries: list[TimelineEntry] = build_timeline(events, max_events=400, anchor=incident.created_at)
    findings = correlate(events, trigger_time=incident.created_at)

    return EvidencePackage(
        incident_id=incident.incident_id,
        trigger_name=incident.trigger_name,
        trigger_reason=incident.trigger_reason,
        event_counts_by_source=dict(Counter(e.source.value for e in events)),
        timeline=[entry.as_dict() for entry in timeline_entries],
        correlations=findings,
        representative_screenshot=_closest_screenshot(events, incident),
    )


def _closest_screenshot(events: list[Event], incident: Incident) -> str | None:
    screenshots = [e for e in events if e.event_type == "screen.capture"]
    if not screenshots:
        return None
    closest = min(screenshots, key=lambda e: abs((e.timestamp - incident.created_at).total_seconds()))
    return closest.payload.get("image_path")
