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
    def __init__(self, event: Event, offset_seconds: float, summary: str) -> None:
        self.event = event
        self.offset_seconds = offset_seconds
        self.summary = summary

    def as_dict(self) -> dict:
        return {
            "t": round(self.offset_seconds, 2),
            "source": self.event.source.value,
            "type": self.event.event_type,
            "summary": self.summary,
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
        TimelineEntry(event, (event.timestamp - anchor).total_seconds(), _summarize(event))
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
