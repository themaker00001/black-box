from __future__ import annotations

from datetime import datetime

from app.events.models import Event

# High-signal event types are always kept in full; high-frequency/low-signal
# ones (metrics, process snapshots, screenshots) are downsampled so the
# timeline stays a reasonable size for the LLM prompt without losing the story.
_HIGH_SIGNAL_TYPES = {
    "os.crash_report",
    "os.unified_log",
    "process.started",
    "process.terminated",
    "terminal.command",
    "trigger.fired",
}


class TimelineEntry:
    def __init__(self, event: Event, offset_seconds: float, summary: str, label: str, subject: str | None) -> None:
        self.event = event
        self.offset_seconds = offset_seconds
        self.summary = summary
        self.label = label
        self.subject = subject

    def as_dict(self) -> dict:
        return {
            "t": round(self.offset_seconds, 2),
            "source": self.event.source.value,
            "type": self.event.event_type,
            "summary": self.summary,
            "label": self.label,
            "subject": self.subject,
        }


def build_timeline(events: list[Event], max_events: int, anchor: datetime | None = None) -> list[TimelineEntry]:
    if not events:
        return []
    ordered = sorted(events, key=lambda e: e.timestamp)
    anchor = anchor or ordered[-1].timestamp

    high_signal = [e for e in ordered if e.event_type in _HIGH_SIGNAL_TYPES]
    low_signal = [e for e in ordered if e.event_type not in _HIGH_SIGNAL_TYPES]

    budget_for_low_signal = max(max_events - len(high_signal), 0)
    sampled_low_signal = _downsample(low_signal, budget_for_low_signal)

    combined = sorted(high_signal + sampled_low_signal, key=lambda e: e.timestamp)
    return [
        TimelineEntry(
            event,
            (event.timestamp - anchor).total_seconds(),
            _summarize(event),
            _short_label(event),
            _subject(event),
        )
        for event in combined
    ]


def _downsample(events: list[Event], budget: int) -> list[Event]:
    if budget <= 0 or not events:
        return []
    if len(events) <= budget:
        return events
    step = len(events) / budget
    return [events[int(i * step)] for i in range(budget)]


def _summarize(event: Event) -> str:
    p = event.payload
    match event.event_type:
        case "screen.capture":
            return f"screenshot captured (monitor {p.get('monitor_id')})"
        case "system.metrics":
            return (
                f"cpu={p.get('cpu_percent', 0):.1f}% mem={p.get('memory_percent', 0):.1f}% "
                f"net_sent={p.get('net_sent_bytes_per_sec', 0):.0f}B/s"
            )
        case "process.snapshot":
            top = p.get("processes", [])
            top_desc = ", ".join(f"{proc['name']}({proc['cpu_percent']:.0f}%)" for proc in top[:3])
            return f"top processes: {top_desc}" if top_desc else "process snapshot"
        case "process.started":
            return f"process started: {p.get('name')} (pid {p.get('pid')}, ppid {p.get('ppid')})"
        case "process.terminated":
            return f"process terminated: {p.get('name')} (pid {p.get('pid')})"
        case "terminal.command":
            exit_code = p.get("exit_code")
            return f"$ {p.get('command')}  [exit={exit_code}]" if exit_code is not None else f"$ {p.get('command')}"
        case "os.crash_report":
            return f"CRASH REPORT: {p.get('process_name')} — {p.get('message')} (signal={p.get('signal')})"
        case "os.unified_log":
            return f"log: {p.get('message', '')[:200]}"
        case "trigger.fired":
            return f"TRIGGER ({p.get('trigger_name')}): {p.get('reason')}"
        case _:
            return event.event_type


def _short_label(event: Event) -> str:
    """A compact, identity-first label for graph nodes — 'what the thing is',
    not just 'an event of this type happened'."""
    p = event.payload
    match event.event_type:
        case "screen.capture":
            return "Screenshot"
        case "system.metrics":
            return f"CPU {p.get('cpu_percent', 0):.0f}%"
        case "process.snapshot":
            top = p.get("processes", [])
            return top[0]["name"] if top else "Processes"
        case "process.started":
            return f"▶ {p.get('name', '?')}"
        case "process.terminated":
            return f"■ {p.get('name', '?')}"
        case "terminal.command":
            command = p.get("command", "")
            return command if len(command) <= 22 else command[:21] + "…"
        case "os.crash_report":
            return f"{p.get('process_name', 'process')} crashed"
        case "os.unified_log":
            message = p.get("message", "")
            return message if len(message) <= 22 else message[:21] + "…"
        case "trigger.fired":
            return str(p.get("trigger_name", "trigger"))
        case _:
            return event.event_type


def _subject(event: Event) -> str | None:
    """The process this event is 'about', when there is one — used to promote
    the single most relevant process into its own hub node in the graph."""
    p = event.payload
    if event.event_type in ("process.started", "process.terminated") and p.get("name"):
        return f"{p['name']} (pid {p.get('pid')})"
    if event.event_type == "os.crash_report" and p.get("process_name"):
        return f"{p['process_name']} (pid {p.get('pid')})" if p.get("pid") else p["process_name"]
    return None
