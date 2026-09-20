from __future__ import annotations

from datetime import datetime, timedelta

from app.events.models import Event

"""Deterministic evidence-lookup helpers used when building agent prompts or
verifying a claim after the fact. These are plain functions, not a live
tool-calling loop into the LLM — for a local single-shot debugging agent that
keeps the system simple and every result reproducible without depending on a
model's tool-use support."""


def events_near(events: list[Event], timestamp: datetime, window_seconds: float) -> list[Event]:
    return [e for e in events if abs((e.timestamp - timestamp).total_seconds()) <= window_seconds]


def events_for_pid(events: list[Event], pid: int) -> list[Event]:
    matches = []
    for e in events:
        payload_pid = e.payload.get("pid")
        if payload_pid == pid:
            matches.append(e)
            continue
        for proc in e.payload.get("processes", []) if e.event_type == "process.snapshot" else []:
            if proc.get("pid") == pid:
                matches.append(e)
                break
    return matches


def terminal_commands_before(events: list[Event], anchor: datetime, window_seconds: float) -> list[Event]:
    return [
        e
        for e in events
        if e.event_type == "terminal.command" and 0 <= (anchor - e.timestamp).total_seconds() <= window_seconds
    ]


def format_bytes_per_sec(value: float) -> str:
    for unit in ("B/s", "KB/s", "MB/s", "GB/s"):
        if value < 1024:
            return f"{value:.1f}{unit}"
        value /= 1024
    return f"{value:.1f}TB/s"
