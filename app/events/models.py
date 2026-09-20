from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _event_id() -> str:
    return uuid.uuid4().hex


class EventSource(str, Enum):
    SCREEN = "screen"
    SYSTEM = "system"
    PROCESS = "process"
    TERMINAL = "terminal"
    OS_EVENT = "os_event"
    TRIGGER = "trigger"


class Event(BaseModel):
    """The single normalized shape every collector and consumer speaks."""

    event_id: str = Field(default_factory=_event_id)
    timestamp: datetime = Field(default_factory=_now)
    source: EventSource
    event_type: str
    payload: dict[str, Any] = Field(default_factory=dict)

    def age_seconds(self, at: datetime | None = None) -> float:
        return ((at or _now()) - self.timestamp).total_seconds()


class ScreenCapturePayload(BaseModel):
    monitor_id: int
    image_path: str
    width: int
    height: int


class SystemMetricsPayload(BaseModel):
    cpu_percent: float
    cpu_per_core: list[float] = Field(default_factory=list)
    memory_percent: float
    memory_available_mb: float
    memory_used_mb: float
    swap_percent: float
    disk_read_bytes_per_sec: float
    disk_write_bytes_per_sec: float
    net_sent_bytes_per_sec: float
    net_recv_bytes_per_sec: float
    gpu_utilization_percent: float | None = None
    gpu_memory_used_mb: float | None = None
    gpu_name: str | None = None


class ProcessInfo(BaseModel):
    pid: int
    ppid: int | None = None
    name: str
    cmdline: str = ""
    cpu_percent: float = 0.0
    memory_percent: float = 0.0
    memory_mb: float = 0.0
    status: str = ""
    create_time: float | None = None


class ProcessSnapshotPayload(BaseModel):
    processes: list[ProcessInfo]
    total_process_count: int


class ProcessLifecyclePayload(BaseModel):
    """Emitted when the process collector notices a start/exit between polls."""

    pid: int
    name: str
    cmdline: str = ""
    lifecycle: str  # "started" | "terminated"
    ppid: int | None = None


class TerminalCommandPayload(BaseModel):
    shell: str
    command: str
    exit_code: int | None = None
    stdout: str | None = None
    stderr: str | None = None
    cwd: str | None = None
    duration_seconds: float | None = None


class OsEventPayload(BaseModel):
    category: str  # "crash_report" | "unified_log" | "app_termination" | "signal"
    process_name: str | None = None
    pid: int | None = None
    signal: str | None = None
    message: str = ""
    raw_source: str | None = None


class TriggerPayload(BaseModel):
    reason: str
    trigger_name: str
    details: dict[str, Any] = Field(default_factory=dict)
