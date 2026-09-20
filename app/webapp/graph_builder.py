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


def build_incident_graph(evidence: EvidencePackage, analysis_text: str) -> dict:
    """A mind-map-style node/edge graph for Cytoscape: a trigger+root-cause hub,
    correlation findings as spokes off that hub, and a chronological chain of
    the highest-signal timeline events — so the shape itself tells the story."""
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

    high_signal = [e for e in evidence.timeline if e["type"] in _HIGH_SIGNAL_TYPES][:_MAX_EVIDENCE_NODES]
    previous_id: str | None = None
    for i, entry in enumerate(high_signal):
        node_id = f"evt_{i}"
        nodes.append(
            {
                "data": {
                    "id": node_id,
                    "label": f"t={entry['t']:+.1f}s\n{entry['source']}",
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
