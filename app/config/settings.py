from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config.yaml"


def _expand(path: str) -> Path:
    return Path(os.path.expanduser(os.path.expandvars(path)))


class BufferSettings(BaseModel):
    retention_seconds: float = 300
    pre_incident_seconds: float = 300
    post_incident_seconds: float = 5


class ScreenCaptureSettings(BaseModel):
    enabled: bool = True
    interval_seconds: float = 1.0
    monitor: str = "all"
    storage_dir: Path = Path("~/.blackbox/screenshots")
    max_dimension: int = 1600


class SystemCaptureSettings(BaseModel):
    enabled: bool = True
    interval_seconds: float = 2.0
    collect_gpu: bool = True


class ProcessCaptureSettings(BaseModel):
    enabled: bool = True
    interval_seconds: float = 2.0
    top_n_by_cpu: int = 15
    top_n_by_memory: int = 15


class TerminalCaptureSettings(BaseModel):
    enabled: bool = False
    event_log_path: Path = Path("~/.blackbox/terminal_events.jsonl")
    capture_stdout: bool = False
    capture_stderr: bool = False
    max_output_chars: int = 2000
    redact_patterns: list[str] = Field(default_factory=list)


class OsEventsCaptureSettings(BaseModel):
    enabled: bool = True
    poll_interval_seconds: float = 2.0
    diagnostic_reports_dir: Path = Path("~/Library/Logs/DiagnosticReports")
    unified_log_predicate: str = ""


class CaptureSettings(BaseModel):
    screen: ScreenCaptureSettings = ScreenCaptureSettings()
    system: SystemCaptureSettings = SystemCaptureSettings()
    processes: ProcessCaptureSettings = ProcessCaptureSettings()
    terminal: TerminalCaptureSettings = TerminalCaptureSettings()
    os_events: OsEventsCaptureSettings = OsEventsCaptureSettings()


class CrashDetectorSettings(BaseModel):
    enabled: bool = True


class ExceptionDetectorSettings(BaseModel):
    enabled: bool = True


class SystemDetectorSettings(BaseModel):
    enabled: bool = True
    cpu_percent_threshold: float = 95
    memory_percent_threshold: float = 95
    sustained_seconds: float = 10


class ManualTriggerSettings(BaseModel):
    enabled: bool = True
    signal_file: Path = Path("~/.blackbox/trigger_now")
    poll_interval_seconds: float = 1.0


class TriggerSettings(BaseModel):
    crash_detector: CrashDetectorSettings = CrashDetectorSettings()
    exception_detector: ExceptionDetectorSettings = ExceptionDetectorSettings()
    system_detector: SystemDetectorSettings = SystemDetectorSettings()
    manual_trigger: ManualTriggerSettings = ManualTriggerSettings()


class IncidentSettings(BaseModel):
    output_dir: Path = Path("incidents")
    max_open_incidents: int = 3


class LlmSettings(BaseModel):
    provider: str = "ollama"
    host: str = "http://localhost:11434"
    model: str = "qwen3:14b"
    request_timeout_seconds: float = 180
    temperature: float = 0.2
    max_context_events: int = 400


class StorageSettings(BaseModel):
    database_path: Path = Path("incidents/blackbox.db")


class LoggingSettings(BaseModel):
    level: str = "INFO"
    log_dir: Path = Path("~/.blackbox/logs")


class WebSettings(BaseModel):
    enabled: bool = True
    host: str = "127.0.0.1"
    port: int = 8765


class Settings(BaseModel):
    buffer: BufferSettings = BufferSettings()
    capture: CaptureSettings = CaptureSettings()
    triggers: TriggerSettings = TriggerSettings()
    incident: IncidentSettings = IncidentSettings()
    llm: LlmSettings = LlmSettings()
    storage: StorageSettings = StorageSettings()
    logging: LoggingSettings = LoggingSettings()
    web: WebSettings = WebSettings()

    def resolved(self) -> "Settings":
        """Return a copy with every filesystem path expanded (~, env vars)."""
        data: dict[str, Any] = self.model_dump()
        data["capture"]["screen"]["storage_dir"] = _expand(str(self.capture.screen.storage_dir))
        data["capture"]["terminal"]["event_log_path"] = _expand(str(self.capture.terminal.event_log_path))
        data["capture"]["os_events"]["diagnostic_reports_dir"] = _expand(
            str(self.capture.os_events.diagnostic_reports_dir)
        )
        data["triggers"]["manual_trigger"]["signal_file"] = _expand(
            str(self.triggers.manual_trigger.signal_file)
        )
        data["incident"]["output_dir"] = _expand(str(self.incident.output_dir))
        data["storage"]["database_path"] = _expand(str(self.storage.database_path))
        data["logging"]["log_dir"] = _expand(str(self.logging.log_dir))
        return Settings.model_validate(data)


def load_settings(path: str | Path | None = None) -> Settings:
    config_path = Path(path) if path else DEFAULT_CONFIG_PATH
    if not config_path.exists():
        return Settings().resolved()
    with open(config_path, "r") as f:
        raw = yaml.safe_load(f) or {}
    return Settings.model_validate(raw).resolved()


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return load_settings()
