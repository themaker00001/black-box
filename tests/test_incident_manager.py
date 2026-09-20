import time

from app.buffer.circular_buffer import CircularBuffer
from app.config.settings import IncidentSettings
from app.events.models import Event, EventSource, TriggerPayload
from app.incident.manager import IncidentManager


def test_trigger_produces_incident_with_buffered_events(tmp_path):
    buf = CircularBuffer(retention_seconds=300)
    for i in range(3):
        buf.add(Event(source=EventSource.SYSTEM, event_type="system.metrics", payload={"i": i}))

    results = []
    manager = IncidentManager(
        buffer=buf,
        settings=IncidentSettings(output_dir=tmp_path, max_open_incidents=3),
        pre_incident_seconds=300,
        post_incident_seconds=0.2,
        on_incident_ready=lambda incident, events: results.append((incident, events)),
    )

    manager.handle_trigger(TriggerPayload(reason="test", trigger_name="manual_trigger"))
    time.sleep(0.6)

    assert len(results) == 1
    incident, events = results[0]
    assert incident.trigger_reason == "test"
    assert len(events) == 3
    assert (tmp_path / incident.incident_id / "raw_events.json").exists()


def test_max_open_incidents_drops_extra_triggers(tmp_path):
    buf = CircularBuffer(retention_seconds=300)
    results = []
    manager = IncidentManager(
        buffer=buf,
        settings=IncidentSettings(output_dir=tmp_path, max_open_incidents=1),
        pre_incident_seconds=300,
        post_incident_seconds=1.0,
        on_incident_ready=lambda incident, events: results.append(incident),
    )

    manager.handle_trigger(TriggerPayload(reason="first", trigger_name="manual_trigger"))
    manager.handle_trigger(TriggerPayload(reason="second", trigger_name="manual_trigger"))
    time.sleep(1.5)

    assert len(results) == 1
    assert results[0].trigger_reason == "first"
