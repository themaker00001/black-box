from __future__ import annotations

from app.evidence.processor import EvidencePackage
from app.webapp.analysis_parser import parse_analysis

_HIGH_SIGNAL_TYPES = {
    "os.crash_report",
    "os.unified_log",
    "process.started",
    "process.terminated",
    "terminal.command",
    "trigger.fired",
}
_MAX_EVIDENCE_NODES = 25


def _extract_root_cause(analysis_text: str) -> str:
    sections = parse_analysis(analysis_text)
    return sections.most_likely_cause or analysis_text.strip()[:300] or "No AI analysis available"


def _pick_subject_entry(high_signal: list[dict]) -> dict | None:
    """The single process/entity this incident is 'about', if one is evident —
    a crash report wins outright; otherwise the first process lifecycle event.
    Promoting it into its own hub node is what answers 'what is the thing'
    at a glance, instead of making the reader open every node to find out."""
    for entry in high_signal:
        if entry["type"] == "os.crash_report" and entry.get("subject"):
            return entry
    for entry in high_signal:
        if entry["type"] in ("process.started", "process.terminated") and entry.get("subject"):
            return entry
    return None


def build_incident_graph(evidence: EvidencePackage, analysis_text: str) -> dict:
    """A mind-map-style node/edge graph for Cytoscape: a trigger+root-cause hub,
    the implicated process promoted to its own subject node, correlation
    findings as spokes, and a chronological chain of the highest-signal
    timeline events — so the shape itself tells the story."""
    nodes: list[dict] = []
    edges: list[dict] = []

    nodes.append(
        {
            "data": {
                "id": "trigger",
                "label": f"TRIGGER\n{evidence.trigger_name}",
                "kind": "trigger",
                "detail": evidence.trigger_reason,
            }
        }
    )
    nodes.append(
        {
            "data": {
                "id": "root_cause",
                "label": "Most Likely Cause",
                "kind": "root_cause",
                "detail": _extract_root_cause(analysis_text),
            }
        }
    )
    edges.append({"data": {"id": "trigger-root_cause", "source": "trigger", "target": "root_cause"}})

    high_signal = [e for e in evidence.timeline if e["type"] in _HIGH_SIGNAL_TYPES][:_MAX_EVIDENCE_NODES]
    subject_entry = _pick_subject_entry(high_signal)
    if subject_entry:
        nodes.append(
            {
                "data": {
                    "id": "subject",
                    "label": f"⬤ {subject_entry['subject']}",
                    "kind": "subject",
                    "detail": subject_entry["summary"],
                }
            }
        )
        edges.append({"data": {"id": "trigger-subject", "source": "trigger", "target": "subject"}})
        edges.append({"data": {"id": "root_cause-subject", "source": "root_cause", "target": "subject"}})

    for i, finding in enumerate(evidence.correlations):
        node_id = f"corr_{i}"
        nodes.append(
            {
                "data": {
                    "id": node_id,
                    "label": finding.kind.replace("_", " "),
                    "kind": "correlation",
                    "detail": finding.description,
                }
            }
        )
        edges.append({"data": {"id": f"root_cause-{node_id}", "source": "root_cause", "target": node_id}})

    if evidence.representative_screenshot:
        nodes.append(
            {
                "data": {
                    "id": "screenshot",
                    "label": "Screen at incident time",
                    "kind": "screenshot",
                    "detail": evidence.representative_screenshot,
                }
            }
        )
        edges.append({"data": {"id": "trigger-screenshot", "source": "trigger", "target": "screenshot"}})

    previous_id: str | None = "subject" if subject_entry else None
    for i, entry in enumerate(high_signal):
        if entry is subject_entry:
            continue
        node_id = f"evt_{i}"
        nodes.append(
            {
                "data": {
                    "id": node_id,
                    "label": f"{entry['label']}\nt={entry['t']:+.1f}s",
                    "kind": "event",
                    "detail": entry["summary"],
                }
            }
        )
        if previous_id:
            edges.append({"data": {"id": f"{previous_id}-{node_id}", "source": previous_id, "target": node_id}})
        else:
            edges.append({"data": {"id": f"trigger-{node_id}", "source": "trigger", "target": node_id}})
        previous_id = node_id

    return {"nodes": nodes, "edges": edges}
