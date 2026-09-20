from __future__ import annotations

import logging
import subprocess
import threading
import time

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
