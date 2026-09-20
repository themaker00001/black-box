from __future__ import annotations

import logging
import threading

import psutil

from app.config.settings import ProcessCaptureSettings
from app.events.bus import EventBus
from app.events.models import ProcessInfo, ProcessLifecyclePayload, ProcessSnapshotPayload
from app.events.normalizer import process_lifecycle_event, process_snapshot_event

logger = logging.getLogger(__name__)

PROCESS_FIELDS = ["pid", "ppid", "name", "cmdline", "cpu_percent", "memory_percent", "status", "create_time"]


def _to_process_info(info: dict) -> ProcessInfo:
    cmdline = info.get("cmdline") or []
    return ProcessInfo(
        pid=info["pid"],
        ppid=info.get("ppid"),
        name=info.get("name") or "",
        cmdline=" ".join(cmdline),
        cpu_percent=info.get("cpu_percent") or 0.0,
        memory_percent=info.get("memory_percent") or 0.0,
        memory_mb=(info.get("memory_percent") or 0.0) / 100.0 * psutil.virtual_memory().total / (1024 * 1024),
        status=info.get("status") or "",
        create_time=info.get("create_time"),
    )


class ProcessCollector:
    """Builds on the existing psutil.process_iter approach: takes periodic
    snapshots of every process and diffs consecutive snapshots to notice
    processes starting or disappearing (a strong signal right before a crash)."""

    def __init__(self, bus: EventBus, settings: ProcessCaptureSettings) -> None:
        self._bus = bus
        self._settings = settings
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._known_pids: dict[int, ProcessInfo] = {}

    def start(self) -> None:
        if self._thread is not None:
            return
        self._thread = threading.Thread(target=self._run, name="process-collector", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5)
            self._thread = None

    def _run(self) -> None:
        while not self._stop_event.wait(self._settings.interval_seconds):
            self._poll_once()

    def _poll_once(self) -> None:
        current: dict[int, ProcessInfo] = {}
        for proc in psutil.process_iter(PROCESS_FIELDS):
            try:
                current[proc.info["pid"]] = _to_process_info(proc.info)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
            except Exception:
                logger.exception("unexpected error reading process info")

        self._emit_lifecycle_diff(current)
        self._emit_snapshot(current)
        self._known_pids = current

    def _emit_lifecycle_diff(self, current: dict[int, ProcessInfo]) -> None:
        if not self._known_pids:
            return  # first poll establishes the baseline; nothing "started" relative to nothing
        started = current.keys() - self._known_pids.keys()
        terminated = self._known_pids.keys() - current.keys()

        for pid in started:
            proc = current[pid]
            self._bus.publish(
                process_lifecycle_event(
                    ProcessLifecyclePayload(
                        pid=pid, name=proc.name, cmdline=proc.cmdline, lifecycle="started", ppid=proc.ppid
                    )
                )
            )
        for pid in terminated:
            proc = self._known_pids[pid]
            self._bus.publish(
                process_lifecycle_event(
                    ProcessLifecyclePayload(
                        pid=pid, name=proc.name, cmdline=proc.cmdline, lifecycle="terminated", ppid=proc.ppid
                    )
                )
            )

    def _emit_snapshot(self, current: dict[int, ProcessInfo]) -> None:
        by_cpu = sorted(current.values(), key=lambda p: p.cpu_percent, reverse=True)[: self._settings.top_n_by_cpu]
        by_mem = sorted(current.values(), key=lambda p: p.memory_percent, reverse=True)[
            : self._settings.top_n_by_memory
        ]
        seen_pids: set[int] = set()
        merged: list[ProcessInfo] = []
        for proc in by_cpu + by_mem:
            if proc.pid not in seen_pids:
                seen_pids.add(proc.pid)
                merged.append(proc)

        self._bus.publish(
            process_snapshot_event(
                ProcessSnapshotPayload(processes=merged, total_process_count=len(current))
            )
        )
