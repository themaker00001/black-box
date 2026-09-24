import time

from app.capture.os_events import OsEventsCollector
from app.capture.processes import ProcessCollector
from app.capture.screen import ScreenCollector
from app.capture.system import SystemMetricsCollector
from app.capture.terminal import TerminalCollector
from app.config.settings import (
    OsEventsCaptureSettings,
    ProcessCaptureSettings,
    ScreenCaptureSettings,
    SystemCaptureSettings,
    TerminalCaptureSettings,
)
from app.events.bus import EventBus

# Regression coverage for a real bug: every collector reuses a single
# threading.Event to signal its run-loop to stop. stop() sets it but nothing
# ever cleared it again, so a second start() after a stop() would see the
# event already set and the run-loop would exit on its very first check —
# the collector looked "started" (a live thread existed) but silently
# produced nothing. This only became reachable once collectors could be
# toggled at runtime instead of started once for the process's lifetime.


def test_screen_collector_stop_event_clears_on_restart(tmp_path):
    bus = EventBus()
    c = ScreenCollector(bus, ScreenCaptureSettings(storage_dir=tmp_path))
    c.start()
    assert not c._stop_event.is_set()
    c.stop()
    assert c._stop_event.is_set()
    c.start()
    assert not c._stop_event.is_set()
    c.stop()


def test_system_collector_stop_event_clears_on_restart():
    bus = EventBus()
    c = SystemMetricsCollector(bus, SystemCaptureSettings())
    c.start()
    c.stop()
    assert c._stop_event.is_set()
    c.start()
    assert not c._stop_event.is_set()
    c.stop()


def test_process_collector_stop_event_clears_on_restart():
    bus = EventBus()
    c = ProcessCollector(bus, ProcessCaptureSettings())
    c.start()
    c.stop()
    assert c._stop_event.is_set()
    c.start()
    assert not c._stop_event.is_set()
    c.stop()


def test_terminal_collector_stop_event_clears_on_restart(tmp_path):
    bus = EventBus()
    c = TerminalCollector(bus, TerminalCaptureSettings(enabled=True, event_log_path=tmp_path / "events.jsonl"))
    c.start()
    c.stop()
    assert c._stop_event.is_set()
    c.start()
    assert not c._stop_event.is_set()
    c.stop()


def test_os_events_collector_stop_event_clears_on_restart(tmp_path):
    bus = EventBus()
    c = OsEventsCollector(bus, OsEventsCaptureSettings(diagnostic_reports_dir=tmp_path))
    c.start()
    c.stop()
    assert c._stop_event.is_set()
    c.start()
    assert not c._stop_event.is_set()
    c.stop()


def wait_for(predicate, timeout=8.0):
    """Polls until predicate() is true. A real screen grab + PNG encode takes
    long enough (and varies enough with machine load) that a fixed sleep makes
    these tests fail for reasons that have nothing to do with the code."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.05)
    return False


def test_screen_collector_actually_resumes_capturing_after_restart(tmp_path):
    """End-to-end confirmation (not just the internal flag) for one collector:
    events keep flowing after a stop()/start() cycle, not just before it."""
    bus = EventBus()
    seen = []
    bus.subscribe(lambda e: seen.append(e))
    c = ScreenCollector(bus, ScreenCaptureSettings(interval_seconds=0.2, storage_dir=tmp_path))

    c.start()
    assert wait_for(lambda: len(seen) > 0), "collector never captured anything to begin with"
    c.stop()
    count_before_restart = len(seen)

    c.start()
    resumed = wait_for(lambda: len(seen) > count_before_restart)
    c.stop()

    assert resumed


def test_screen_collector_set_enabled_toggles_capture(tmp_path):
    bus = EventBus()
    seen = []
    bus.subscribe(lambda e: seen.append(e))
    c = ScreenCollector(bus, ScreenCaptureSettings(enabled=False, interval_seconds=0.2, storage_dir=tmp_path))

    c.start()  # disabled: should not start
    time.sleep(0.3)
    assert seen == []

    c.set_enabled(True)
    assert wait_for(lambda: len(seen) > 0), "enabling did not resume capture"

    c.set_enabled(False)
    count_after_disable = len(seen)
    time.sleep(0.6)
    assert len(seen) == count_after_disable  # no new events once disabled again
