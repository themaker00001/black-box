from __future__ import annotations

import json
import logging
import subprocess
import threading
import time
from pathlib import Path

import psutil

from app.config.settings import SystemCaptureSettings
from app.events.bus import EventBus
from app.events.models import SystemMetricsPayload
from app.events.normalizer import system_metrics_event

logger = logging.getLogger(__name__)


def _read_apple_silicon_gpu() -> dict | None:
    """Best-effort GPU utilization for Apple Silicon via ioreg.
    Returns None on Intel Macs, sandboxed environments, or any parsing failure —
    GPU visibility is a bonus, never a requirement."""
    try:
        result = subprocess.run(
            ["ioreg", "-r", "-d", "1", "-w", "0", "-c", "IOAccelerator"],
            capture_output=True,
            text=True,
            timeout=2,
        )
    except Exception:
        return None
    if result.returncode != 0 or not result.stdout:
        return None

    utilization = None
    name = None
    for line in result.stdout.splitlines():
        line = line.strip()
        if '"Device Utilization %"' in line:
            try:
                utilization = float(line.split("=")[-1].strip())
            except ValueError:
                pass
        if '"IOClass"' in line and name is None:
            name = line.split("=")[-1].strip().strip('"')
    if utilization is None:
        return None
    return {"gpu_utilization_percent": utilization, "gpu_name": name}


class SystemMetricsCollector:
    """Machine-level telemetry: CPU, memory, disk I/O, network I/O, best-effort GPU."""

    def __init__(self, bus: EventBus, settings: SystemCaptureSettings) -> None:
        self._bus = bus
        self._settings = settings
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._gpu_available = settings.collect_gpu

    def start(self) -> None:
        if self._thread is not None:
            return
        self._stop_event.clear()
        psutil.cpu_percent(percpu=True)  # prime the internal sampler
        self._thread = threading.Thread(target=self._run, name="system-collector", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5)
            self._thread = None

    def _run(self) -> None:
        last_disk = psutil.disk_io_counters()
        last_net = psutil.net_io_counters()
        last_time = time.monotonic()

        while not self._stop_event.wait(self._settings.interval_seconds):
            now = time.monotonic()
            elapsed = max(now - last_time, 1e-6)

            disk = psutil.disk_io_counters()
            net = psutil.net_io_counters()
            vm = psutil.virtual_memory()
            swap = psutil.swap_memory()

            gpu = self._read_gpu()

            payload = SystemMetricsPayload(
                cpu_percent=psutil.cpu_percent(),
                cpu_per_core=psutil.cpu_percent(percpu=True),
                memory_percent=vm.percent,
                memory_available_mb=vm.available / (1024 * 1024),
                memory_used_mb=vm.used / (1024 * 1024),
                swap_percent=swap.percent,
                disk_read_bytes_per_sec=(disk.read_bytes - last_disk.read_bytes) / elapsed if disk and last_disk else 0.0,
                disk_write_bytes_per_sec=(disk.write_bytes - last_disk.write_bytes) / elapsed if disk and last_disk else 0.0,
                net_sent_bytes_per_sec=(net.bytes_sent - last_net.bytes_sent) / elapsed,
                net_recv_bytes_per_sec=(net.bytes_recv - last_net.bytes_recv) / elapsed,
                gpu_utilization_percent=gpu.get("gpu_utilization_percent") if gpu else None,
                gpu_memory_used_mb=gpu.get("gpu_memory_used_mb") if gpu else None,
                gpu_name=gpu.get("gpu_name") if gpu else None,
            )
            self._bus.publish(system_metrics_event(payload))

            last_disk, last_net, last_time = disk, net, now

    def _read_gpu(self) -> dict | None:
        if not self._gpu_available:
            return None
        gpu = _read_apple_silicon_gpu()
        if gpu is None:
            # Stop retrying every cycle once we know it's unavailable on this machine.
            self._gpu_available = False
        return gpu


def parse_native_sysmon_line(line: str) -> SystemMetricsPayload | None:
    """Turns one JSON line from the native/sysmon binary into a payload.
    Pure and side-effect-free so it's testable without spawning the process.
    Disk I/O isn't sampled by the native binary (see native/README.md), so
    those two fields are reported as 0.0 rather than left out."""
    line = line.strip()
    if not line:
        return None
    try:
        raw = json.loads(line)
    except json.JSONDecodeError:
        logger.warning("skipping malformed sysmon line: %r", line[:200])
        return None

    try:
        return SystemMetricsPayload(
            cpu_percent=raw["cpu_percent"],
            cpu_per_core=raw.get("cpu_per_core", []),
            memory_percent=raw["memory_percent"],
            memory_available_mb=raw["memory_available_mb"],
            memory_used_mb=raw["memory_used_mb"],
            swap_percent=raw["swap_percent"],
            disk_read_bytes_per_sec=0.0,
            disk_write_bytes_per_sec=0.0,
            net_sent_bytes_per_sec=raw["net_sent_bytes_per_sec"],
            net_recv_bytes_per_sec=raw["net_recv_bytes_per_sec"],
        )
    except KeyError:
        logger.warning("sysmon line missing expected fields: %r", line[:200])
        return None


class NativeSystemMetricsCollector:
    """Same job as SystemMetricsCollector, but sourced from the native C++
    sysmon binary instead of psutil — spawned as a subprocess and read line
    by line, exactly like piping any other CLI tool. Falls back to doing
    nothing (and logging why) if the binary isn't built; main.py is
    responsible for choosing this vs. the psutil collector."""

    def __init__(self, bus: EventBus, settings: SystemCaptureSettings) -> None:
        self._bus = bus
        self._settings = settings
        self._process: subprocess.Popen | None = None
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread is not None:
            return
        binary_path = Path(self._settings.native_binary_path)
        if not binary_path.is_file():
            logger.error(
                "native sysmon binary not found at %s (see native/README.md to build it); "
                "system metrics will not be collected",
                binary_path,
            )
            return

        self._process = subprocess.Popen(
            [str(binary_path), str(self._settings.interval_seconds)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        self._thread = threading.Thread(target=self._run, name="native-system-collector", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if self._process:
            self._process.terminate()
            try:
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._process.kill()
            self._process = None
        if self._thread:
            self._thread.join(timeout=5)
            self._thread = None

    def _run(self) -> None:
        assert self._process is not None and self._process.stdout is not None
        for line in self._process.stdout:
            payload = parse_native_sysmon_line(line)
            if payload is not None:
                self._bus.publish(system_metrics_event(payload))
        # The loop exits when the process's stdout closes (crash or stop()).
        return_code = self._process.poll() if self._process else None
        if return_code not in (None, 0, -15):  # -15 == SIGTERM from our own stop()
            stderr = self._process.stderr.read() if self._process and self._process.stderr else ""
            logger.error("native sysmon exited unexpectedly (code %s): %s", return_code, stderr.strip())
