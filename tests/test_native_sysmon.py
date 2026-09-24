import json
import time
from pathlib import Path

import pytest

from app.capture.system import NativeSystemMetricsCollector, parse_native_sysmon_line
from app.config.settings import SystemCaptureSettings
from app.events.bus import EventBus

BINARY_PATH = Path(__file__).resolve().parents[1] / "native" / "build" / "sysmon"
SAMPLE_LINE = (
    '{"cpu_percent":11.88,"cpu_per_core":[33.33,28.0],"memory_percent":65.46,'
    '"memory_used_mb":16087.73,"memory_available_mb":8488.27,"swap_percent":88.44,'
    '"net_sent_bytes_per_sec":1024.0,"net_recv_bytes_per_sec":2048.0}'
)


def test_parse_native_sysmon_line_builds_a_valid_payload():
    payload = parse_native_sysmon_line(SAMPLE_LINE)

    assert payload is not None
    assert payload.cpu_percent == 11.88
    assert payload.cpu_per_core == [33.33, 28.0]
    assert payload.memory_percent == 65.46
    assert payload.net_sent_bytes_per_sec == 1024.0
    # Native sysmon doesn't sample disk I/O — should be reported as 0, not omitted.
    assert payload.disk_read_bytes_per_sec == 0.0
    assert payload.disk_write_bytes_per_sec == 0.0


def test_parse_native_sysmon_line_rejects_malformed_json():
    assert parse_native_sysmon_line("not json") is None


def test_parse_native_sysmon_line_rejects_missing_fields():
    assert parse_native_sysmon_line('{"cpu_percent": 1.0}') is None


def test_parse_native_sysmon_line_ignores_blank_lines():
    assert parse_native_sysmon_line("") is None
    assert parse_native_sysmon_line("   \n") is None


@pytest.mark.skipif(not BINARY_PATH.is_file(), reason="native/build/sysmon not built — see native/README.md")
def test_native_collector_produces_real_events_from_the_compiled_binary():
    bus = EventBus()
    seen = []
    bus.subscribe(lambda e: seen.append(e))

    settings = SystemCaptureSettings(interval_seconds=0.5, native_binary_path=BINARY_PATH)
    collector = NativeSystemMetricsCollector(bus, settings)
    collector.start()
    try:
        time.sleep(1.5)
    finally:
        collector.stop()

    assert len(seen) >= 1
    payload = seen[0].payload
    assert 0.0 <= payload["cpu_percent"] <= 100.0
    assert payload["memory_percent"] > 0.0


@pytest.mark.skipif(not BINARY_PATH.is_file(), reason="native/build/sysmon not built — see native/README.md")
def test_native_binary_output_is_one_json_object_per_line():
    """Validates the binary's raw stdout format directly, independent of the
    Python parser — sysmon runs until killed, so this drives it with Popen
    rather than subprocess.run (which would just raise TimeoutExpired)."""
    import subprocess

    proc = subprocess.Popen([str(BINARY_PATH), "0.2"], stdout=subprocess.PIPE, text=True)
    try:
        lines = [proc.stdout.readline() for _ in range(3)]
    finally:
        proc.terminate()
        proc.wait(timeout=5)

    assert len(lines) == 3
    for line in lines:
        record = json.loads(line)
        assert set(record.keys()) == {
            "cpu_percent",
            "cpu_per_core",
            "memory_percent",
            "memory_used_mb",
            "memory_available_mb",
            "swap_percent",
            "net_sent_bytes_per_sec",
            "net_recv_bytes_per_sec",
        }
