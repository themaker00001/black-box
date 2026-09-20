from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path

from app.agent.debugger import DebugAnalysis
from app.incident.models import Incident

_SCHEMA = """
CREATE TABLE IF NOT EXISTS incidents (
    incident_id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    trigger_name TEXT NOT NULL,
    trigger_reason TEXT NOT NULL,
    event_count INTEGER NOT NULL,
    output_dir TEXT NOT NULL,
    model_used TEXT,
    analysis_succeeded INTEGER,
    analysis_text TEXT,
    report_path TEXT
);
"""


class IncidentStore:
    """Durable, queryable record of past incidents. SQLite because this is a
    single-machine, single-writer tool — no server, no external dependency."""

    def __init__(self, database_path: Path) -> None:
        database_path.parent.mkdir(parents=True, exist_ok=True)
        self._database_path = database_path
        with self._connect() as conn:
            conn.execute(_SCHEMA)

    @contextmanager
    def _connect(self):
        conn = sqlite3.connect(self._database_path)
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def save(self, incident: Incident, analysis: DebugAnalysis, report_path: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO incidents (
                    incident_id, created_at, trigger_name, trigger_reason, event_count,
                    output_dir, model_used, analysis_succeeded, analysis_text, report_path
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(incident_id) DO UPDATE SET
                    analysis_succeeded=excluded.analysis_succeeded,
                    analysis_text=excluded.analysis_text,
                    report_path=excluded.report_path
                """,
                (
                    incident.incident_id,
                    incident.created_at.isoformat(),
                    incident.trigger_name,
                    incident.trigger_reason,
                    incident.event_count,
                    incident.output_dir,
                    analysis.model_used,
                    int(analysis.succeeded),
                    analysis.analysis_text,
                    report_path,
                ),
            )

    def list_recent(self, limit: int = 20) -> list[sqlite3.Row]:
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            return conn.execute(
                "SELECT * FROM incidents ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()

    def get(self, incident_id: str) -> sqlite3.Row | None:
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            return conn.execute(
                "SELECT * FROM incidents WHERE incident_id = ?", (incident_id,)
            ).fetchone()
