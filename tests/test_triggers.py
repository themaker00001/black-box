import time
from datetime import datetime, timedelta, timezone

from app.config.settings import (
    CrashDetectorSettings,
    ExceptionDetectorSettings,
    ManualTriggerSettings,
    SystemDetectorSettings,
)
from app.events.bus import EventBus
from app.events.models import Event, EventSource
from app.events.normalizer import os_event, system_metrics_event, terminal_command_event
from app.events.models import OsEventPayload, SystemMetricsPayload, TerminalCommandPayload
from app.triggers.crash_detector import CrashDetector
from app.triggers.exception_detector import ExceptionDetector
from app.triggers.manual_trigger import ManualTrigger
from app.triggers.system_detector import SystemDetector

NOW = datetime.now(timezone.utc)


def _metrics(cpu: float, at: datetime) -> Event:
    e = system_metrics_event(
        SystemMetricsPayload(
            cpu_percent=cpu, memory_percent=10, memory_available_mb=1, memory_used_mb=1, swap_percent=0,
            disk_read_bytes_per_sec=0, disk_write_bytes_per_sec=0, net_sent_bytes_per_sec=0, net_recv_bytes_per_sec=0,
        )
    )
    e.timestamp = at
    return e


def test_crash_detector_fires_on_crash_report():
    fired = []
    bus = EventBus()
    CrashDetector(bus, CrashDetectorSettings(enabled=True), fired.append)

    bus.publish(os_event(OsEventPayload(category="crash_report", process_name="Safari", message="boom")))

    assert len(fired) == 1
    assert fired[0].trigger_name == "crash_detector"


def test_crash_detector_ignores_non_crash_os_events():
    fired = []
    bus = EventBus()
    CrashDetector(bus, CrashDetectorSettings(enabled=True), fired.append)

    bus.publish(os_event(OsEventPayload(category="unified_log", message="nothing interesting")))

    assert fired == []


def test_disabled_crash_detector_never_subscribes():
    fired = []
    bus = EventBus()
    CrashDetector(bus, CrashDetectorSettings(enabled=False), fired.append)

    bus.publish(os_event(OsEventPayload(category="crash_report", process_name="Safari", message="boom")))

    assert fired == []


def test_exception_detector_fires_on_traceback_with_nonzero_exit():
    fired = []
    bus = EventBus()
    ExceptionDetector(bus, ExceptionDetectorSettings(enabled=True), fired.append)

    bus.publish(
        terminal_command_event(
            TerminalCommandPayload(shell="zsh", command="python x.py", exit_code=1, stderr="Traceback (most recent call last)")
        )
    )

    assert len(fired) == 1


def test_exception_detector_ignores_clean_exit():
    fired = []
    bus = EventBus()
    ExceptionDetector(bus, ExceptionDetectorSettings(enabled=True), fired.append)

    bus.publish(
        terminal_command_event(TerminalCommandPayload(shell="zsh", command="python x.py", exit_code=0, stderr=""))
    )

    assert fired == []


def test_system_detector_fires_once_after_sustained_breach_and_rearms():
    fired = []
    bus = EventBus()
    settings = SystemDetectorSettings(enabled=True, cpu_percent_threshold=90, sustained_seconds=2)
    SystemDetector(bus, settings, fired.append)

    bus.publish(_metrics(95, NOW))
    bus.publish(_metrics(95, NOW + timedelta(seconds=1)))
    bus.publish(_metrics(95, NOW + timedelta(seconds=3)))  # sustained_for >= 2 here
    bus.publish(_metrics(95, NOW + timedelta(seconds=4)))  # should not fire again while still breaching

    assert len(fired) == 1

    bus.publish(_metrics(10, NOW + timedelta(seconds=5)))  # recovers, rearms
    bus.publish(_metrics(95, NOW + timedelta(seconds=6)))
    bus.publish(_metrics(95, NOW + timedelta(seconds=9)))

    assert len(fired) == 2


def test_manual_trigger_consumes_signal_file(tmp_path):
    fired = []
    signal_file = tmp_path / "trigger_now"
    trigger = ManualTrigger(
        ManualTriggerSettings(enabled=True, signal_file=signal_file, poll_interval_seconds=0.1), fired.append
    )
    trigger.start()
    try:
        signal_file.write_text("investigate this")
        time.sleep(0.5)
    finally:
        trigger.stop()

    assert len(fired) == 1
    assert fired[0].reason == "investigate this"
    assert not signal_file.exists()
