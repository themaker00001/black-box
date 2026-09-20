from datetime import datetime, timedelta, timezone

from app.buffer.circular_buffer import CircularBuffer
from app.config.settings import SystemDetectorSettings
from app.evidence.correlation import CorrelationFinding
from app.evidence.processor import EvidencePackage
from app.events.models import Event, EventSource
from app.webapp.graph_builder import build_incident_graph
from app.webapp.status import build_status

NOW = datetime.now(timezone.utc)


def _metrics_event(cpu: float, memory: float) -> Event:
    return Event(source=EventSource.SYSTEM, event_type="system.metrics", payload={"cpu_percent": cpu, "memory_percent": memory})


def test_status_is_ok_when_metrics_are_normal_and_no_recent_incident():
    buf = CircularBuffer(retention_seconds=60)
    buf.add(_metrics_event(20, 30))
    thresholds = SystemDetectorSettings(cpu_percent_threshold=90, memory_percent_threshold=90)

    status = build_status(buf, thresholds, recent_incidents=[])

    assert status["ok"] is True
    assert status["cpu_percent"] == 20


def test_status_flags_not_ok_when_cpu_breaches_threshold():
    buf = CircularBuffer(retention_seconds=60)
    buf.add(_metrics_event(97, 30))
    thresholds = SystemDetectorSettings(cpu_percent_threshold=90, memory_percent_threshold=90)

    status = build_status(buf, thresholds, recent_incidents=[])

    assert status["ok"] is False


def test_status_flags_not_ok_when_incident_is_recent():
    buf = CircularBuffer(retention_seconds=60)
    buf.add(_metrics_event(10, 10))
    thresholds = SystemDetectorSettings(cpu_percent_threshold=90, memory_percent_threshold=90)
    recent = [{"incident_id": "abc", "created_at": NOW.isoformat()}]

    status = build_status(buf, thresholds, recent_incidents=recent)

    assert status["ok"] is False
    assert status["most_recent_incident_id"] == "abc"


def test_status_ignores_stale_incidents():
    buf = CircularBuffer(retention_seconds=60)
    buf.add(_metrics_event(10, 10))
    thresholds = SystemDetectorSettings(cpu_percent_threshold=90, memory_percent_threshold=90)
    stale = (NOW - timedelta(hours=2)).isoformat()
    recent = [{"incident_id": "abc", "created_at": stale}]

    status = build_status(buf, thresholds, recent_incidents=recent)

    assert status["ok"] is True
    assert status["most_recent_incident_id"] is None


def _evidence(correlations=None) -> EvidencePackage:
    return EvidencePackage(
        incident_id="inc-1",
        trigger_name="crash_detector",
        trigger_reason="crashed",
        event_counts_by_source={"os_event": 1},
        timeline=[
            {
                "t": -2.0,
                "source": "os_event",
                "type": "os.crash_report",
                "summary": "CRASH REPORT: hog",
                "label": "hog crashed",
                "subject": "hog (pid 111)",
            },
            {
                "t": -1.0,
                "source": "process",
                "type": "process.terminated",
                "summary": "process terminated: hog",
                "label": "■ hog",
                "subject": "hog (pid 111)",
            },
        ],
        correlations=correlations or [],
        representative_screenshot="/tmp/x/shot.png",
    )


def test_graph_includes_trigger_root_cause_and_screenshot_nodes():
    graph = build_incident_graph(_evidence(), "## Most Likely Cause\nA segfault in hog.\n## Supporting Evidence\n- x")
    node_ids = {n["data"]["id"] for n in graph["nodes"]}

    assert "trigger" in node_ids
    assert "root_cause" in node_ids
    assert "screenshot" in node_ids


def test_graph_promotes_the_implicated_process_to_a_subject_node():
    graph = build_incident_graph(_evidence(), "## Most Likely Cause\nX")
    subject_nodes = [n for n in graph["nodes"] if n["data"]["kind"] == "subject"]

    assert len(subject_nodes) == 1
    assert "hog" in subject_nodes[0]["data"]["label"]
    edge_pairs = {(e["data"]["source"], e["data"]["target"]) for e in graph["edges"]}
    assert ("trigger", "subject") in edge_pairs
    assert ("root_cause", "subject") in edge_pairs


def test_graph_adds_a_spoke_per_correlation_finding():
    correlations = [CorrelationFinding(kind="crash_matches_termination", description="d")]
    graph = build_incident_graph(_evidence(correlations), "## Most Likely Cause\nX")

    corr_nodes = [n for n in graph["nodes"] if n["data"]["kind"] == "correlation"]
    assert len(corr_nodes) == 1
    assert any(e["data"]["target"] == corr_nodes[0]["data"]["id"] for e in graph["edges"])


def test_graph_chains_high_signal_events_chronologically():
    # crash_report/process.terminated get promoted to the subject node, so use
    # event types that stay as plain chain nodes to isolate chaining behavior.
    evidence = _evidence()
    evidence.timeline = [
        {"t": -2.0, "source": "terminal", "type": "terminal.command", "summary": "$ a", "label": "a", "subject": None},
        {"t": -1.0, "source": "terminal", "type": "terminal.command", "summary": "$ b", "label": "b", "subject": None},
    ]
    graph = build_incident_graph(evidence, "## Most Likely Cause\nX")
    event_nodes = [n["data"]["id"] for n in graph["nodes"] if n["data"]["kind"] == "event"]

    assert len(event_nodes) == 2
    edge_pairs = {(e["data"]["source"], e["data"]["target"]) for e in graph["edges"]}
    assert ("evt_0", "evt_1") in edge_pairs
