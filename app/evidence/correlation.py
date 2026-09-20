from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from app.events.models import Event


class CorrelationFinding(BaseModel):
    kind: str
    description: str


def correlate(events: list[Event], trigger_time: datetime, terminal_window_seconds: float = 60) -> list[CorrelationFinding]:
    """Cheap, explainable heuristics linking events from different sources —
    not a black-box model, so every finding can be quoted back as evidence."""
    findings: list[CorrelationFinding] = []
    findings.extend(_crash_to_lifecycle(events))
    findings.extend(_resource_spike_to_process(events))
    findings.extend(_recent_terminal_activity(events, trigger_time, terminal_window_seconds))
    return findings


def _crash_to_lifecycle(events: list[Event]) -> list[CorrelationFinding]:
    findings: list[CorrelationFinding] = []
    crash_events = [e for e in events if e.event_type == "os.crash_report" and e.payload.get("pid")]
    terminations = {
        e.payload["pid"]: e for e in events if e.event_type == "process.terminated" and e.payload.get("pid")
    }
    for crash in crash_events:
        pid = crash.payload["pid"]
        termination = terminations.get(pid)
        if termination:
            findings.append(
                CorrelationFinding(
                    kind="crash_matches_termination",
                    description=(
                        f"Crash report for pid {pid} ({crash.payload.get('process_name')}) lines up with a "
                        f"process-terminated event for the same pid at "
                        f"{termination.timestamp.isoformat()}."
                    ),
                )
            )
    return findings


def _resource_spike_to_process(events: list[Event]) -> list[CorrelationFinding]:
    metrics = [e for e in events if e.event_type == "system.metrics"]
    if not metrics:
        return []
    peak = max(metrics, key=lambda e: e.payload.get("cpu_percent", 0.0))
    if peak.payload.get("cpu_percent", 0.0) < 80:
        return []

    nearby_snapshot = min(
        (e for e in events if e.event_type == "process.snapshot"),
        key=lambda e: abs((e.timestamp - peak.timestamp).total_seconds()),
        default=None,
    )
    if nearby_snapshot is None:
        return []
    processes = nearby_snapshot.payload.get("processes", [])
    if not processes:
        return []
    top = max(processes, key=lambda p: p.get("cpu_percent", 0.0))
    return [
        CorrelationFinding(
            kind="cpu_spike_process",
            description=(
                f"CPU peaked at {peak.payload.get('cpu_percent'):.1f}% around {peak.timestamp.isoformat()}; "
                f"the closest process snapshot shows '{top.get('name')}' (pid {top.get('pid')}) "
                f"using {top.get('cpu_percent'):.1f}% CPU at that time."
            ),
        )
    ]


def _recent_terminal_activity(events: list[Event], trigger_time: datetime, window_seconds: float) -> list[CorrelationFinding]:
    commands = [
        e
        for e in events
        if e.event_type == "terminal.command" and 0 <= (trigger_time - e.timestamp).total_seconds() <= window_seconds
    ]
    if not commands:
        return []
    lines = [f"'{c.payload.get('command')}' (exit={c.payload.get('exit_code')})" for c in commands]
    return [
        CorrelationFinding(
            kind="recent_terminal_commands",
            description=(
                f"{len(commands)} terminal command(s) ran in the {window_seconds:.0f}s before the trigger: "
                + "; ".join(lines)
            ),
        )
    ]
