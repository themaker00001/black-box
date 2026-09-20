from __future__ import annotations

from app.events.models import (
    Event,
    EventSource,
    OsEventPayload,
    ProcessLifecyclePayload,
    ProcessSnapshotPayload,
    ScreenCapturePayload,
    SystemMetricsPayload,
    TerminalCommandPayload,
    TriggerPayload,
)

"""Thin factories so collectors never construct raw Event(...) calls by hand
and every payload is validated against its Pydantic model before it enters the bus."""


def screen_capture_event(payload: ScreenCapturePayload) -> Event:
    return Event(source=EventSource.SCREEN, event_type="screen.capture", payload=payload.model_dump())


def system_metrics_event(payload: SystemMetricsPayload) -> Event:
    return Event(source=EventSource.SYSTEM, event_type="system.metrics", payload=payload.model_dump())


def process_snapshot_event(payload: ProcessSnapshotPayload) -> Event:
    return Event(source=EventSource.PROCESS, event_type="process.snapshot", payload=payload.model_dump())


def process_lifecycle_event(payload: ProcessLifecyclePayload) -> Event:
    return Event(
        source=EventSource.PROCESS,
        event_type=f"process.{payload.lifecycle}",
        payload=payload.model_dump(),
    )


def terminal_command_event(payload: TerminalCommandPayload) -> Event:
    return Event(source=EventSource.TERMINAL, event_type="terminal.command", payload=payload.model_dump())


def os_event(payload: OsEventPayload) -> Event:
    return Event(source=EventSource.OS_EVENT, event_type=f"os.{payload.category}", payload=payload.model_dump())


def trigger_event(payload: TriggerPayload) -> Event:
    return Event(source=EventSource.TRIGGER, event_type="trigger.fired", payload=payload.model_dump())
