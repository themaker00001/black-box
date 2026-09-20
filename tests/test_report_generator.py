from datetime import datetime, timezone

from app.agent.debugger import DebugAnalysis
from app.evidence.correlation import CorrelationFinding
from app.evidence.processor import EvidencePackage
from app.incident.models import Incident
from app.report.generator import generate_report, write_report


def _incident(output_dir: str) -> Incident:
    return Incident(
        incident_id="test-1",
        created_at=datetime.now(timezone.utc),
        trigger_name="manual_trigger",
        trigger_reason="user requested",
        output_dir=output_dir,
        event_count=2,
    )


def _evidence() -> EvidencePackage:
    return EvidencePackage(
        incident_id="test-1",
        trigger_name="manual_trigger",
        trigger_reason="user requested",
        event_counts_by_source={"system": 2},
        timeline=[{"t": 0.0, "source": "system", "type": "system.metrics", "summary": "cpu=10%"}],
        correlations=[CorrelationFinding(kind="cpu_spike_process", description="something happened")],
        representative_screenshot=None,
    )


def test_generate_report_includes_key_sections():
    incident = _incident("/tmp/whatever")
    analysis = DebugAnalysis(incident_id="test-1", model_used="llama3.2", analysis_text="## Most Likely Cause\nX", succeeded=True)

    report = generate_report(incident, _evidence(), analysis)

    assert "Incident Report: test-1" in report
    assert "Most Likely Cause" in report
    assert "cpu_spike_process" in report
    assert "| 0.0 | system | system.metrics | cpu=10% |" in report


def test_write_report_creates_file_on_disk(tmp_path):
    incident = _incident(str(tmp_path / "test-1"))
    analysis = DebugAnalysis(incident_id="test-1", model_used="llama3.2", analysis_text="analysis", succeeded=True)

    report_path = write_report(incident, _evidence(), analysis)

    assert report_path.exists()
    assert report_path.read_text().startswith("# Incident Report")
