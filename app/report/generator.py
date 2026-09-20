from __future__ import annotations

from pathlib import Path

from app.agent.debugger import DebugAnalysis
from app.evidence.processor import EvidencePackage
from app.incident.models import Incident


def generate_report(incident: Incident, evidence: EvidencePackage, analysis: DebugAnalysis) -> str:
    lines = [
        f"# Incident Report: {incident.incident_id}",
        "",
        f"- **Detected at:** {incident.created_at.isoformat()}",
        f"- **Trigger:** {incident.trigger_name} — {incident.trigger_reason}",
        f"- **Events captured:** {incident.event_count}",
        f"- **Model used:** {analysis.model_used} ({'ok' if analysis.succeeded else 'unavailable'})",
        "",
        "---",
        "",
        analysis.analysis_text,
        "",
        "---",
        "",
        "## Evidence Appendix",
        "",
        f"Event counts by source: {evidence.event_counts_by_source}",
        "",
        "### Correlated Findings",
    ]
    if evidence.correlations:
        lines += [f"- **{c.kind}**: {c.description}" for c in evidence.correlations]
    else:
        lines.append("- none found")

    lines += ["", "### Full Timeline (t=0 is the trigger)", "", "| t (s) | source | type | summary |", "|---|---|---|---|"]
    lines += [f"| {e['t']} | {e['source']} | {e['type']} | {e['summary']} |" for e in evidence.timeline]

    if evidence.representative_screenshot:
        lines += ["", f"Representative screenshot: `{evidence.representative_screenshot}`"]

    return "\n".join(lines) + "\n"


def write_report(incident: Incident, evidence: EvidencePackage, analysis: DebugAnalysis) -> Path:
    output_dir = Path(incident.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "report.md"
    report_path.write_text(generate_report(incident, evidence, analysis))
    return report_path
