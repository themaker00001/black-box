from datetime import datetime, timedelta, timezone

from app.events.models import Event, EventSource
from app.evidence.correlation import correlate
from app.evidence.processor import build_evidence
from app.evidence.timeline import build_timeline
from app.incident.models import Incident

NOW = datetime.now(timezone.utc)


def _ago(seconds: float) -> datetime:
    return NOW - timedelta(seconds=seconds)


def test_timeline_offsets_are_relative_to_anchor():
    events = [
        Event(source=EventSource.SYSTEM, event_type="system.metrics", timestamp=_ago(10), payload={"cpu_percent": 5}),
        Event(source=EventSource.TRIGGER, event_type="trigger.fired", timestamp=NOW, payload={"trigger_name": "x", "reason": "y"}),
    ]
    timeline = build_timeline(events, max_events=100, anchor=NOW)
    offsets = [e.offset_seconds for e in timeline]
    assert offsets[0] < 0
    assert offsets[-1] == 0


def test_timeline_keeps_all_high_signal_events_and_downsamples_the_rest():
    high_signal = [
        Event(source=EventSource.OS_EVENT, event_type="os.crash_report", timestamp=_ago(i), payload={})
        for i in range(5)
    ]
    low_signal = [
        Event(source=EventSource.SYSTEM, event_type="system.metrics", timestamp=_ago(i), payload={"cpu_percent": 1})
        for i in range(100)
    ]
    timeline = build_timeline(high_signal + low_signal, max_events=20, anchor=NOW)

    kept_types = [e.event.event_type for e in timeline]
    assert kept_types.count("os.crash_report") == 5
    assert len(timeline) <= 20


def test_crash_correlates_with_matching_process_termination():
    events = [
        Event(
            source=EventSource.OS_EVENT,
            event_type="os.crash_report",
            timestamp=_ago(2),
            payload={"pid": 42, "process_name": "hog", "message": "segfault"},
        ),
        Event(
            source=EventSource.PROCESS,
            event_type="process.terminated",
            timestamp=_ago(1),
            payload={"pid": 42, "name": "hog"},
        ),
    ]
    findings = correlate(events, trigger_time=NOW)
    assert any(f.kind == "crash_matches_termination" for f in findings)


def test_recent_terminal_commands_are_flagged_within_window():
    events = [
        Event(
            source=EventSource.TERMINAL,
            event_type="terminal.command",
            timestamp=_ago(5),
            payload={"command": "python leaky.py", "exit_code": 0},
        )
    ]
    findings = correlate(events, trigger_time=NOW, terminal_window_seconds=60)
    assert any(f.kind == "recent_terminal_commands" for f in findings)


def test_recent_terminal_commands_outside_window_are_ignored():
    events = [
        Event(
            source=EventSource.TERMINAL,
            event_type="terminal.command",
            timestamp=_ago(500),
            payload={"command": "python leaky.py", "exit_code": 0},
        )
    ]
    findings = correlate(events, trigger_time=NOW, terminal_window_seconds=60)
    assert not any(f.kind == "recent_terminal_commands" for f in findings)


def test_build_evidence_counts_events_by_source():
    incident = Incident.new("manual_trigger", "test", {}, "/tmp/blackbox-test-incidents")
    incident.created_at = NOW
    events = [
        Event(source=EventSource.SYSTEM, event_type="system.metrics", timestamp=_ago(1), payload={"cpu_percent": 1}),
        Event(source=EventSource.PROCESS, event_type="process.snapshot", timestamp=_ago(1), payload={"processes": []}),
    ]
    evidence = build_evidence(incident, events)
    assert evidence.event_counts_by_source == {"system": 1, "process": 1}
