from __future__ import annotations

import logging
import re
import threading
from pathlib import Path
from typing import Protocol

from flask import Flask, abort, jsonify, render_template, request, send_file
from werkzeug.serving import make_server

from app.buffer.circular_buffer import CircularBuffer
from app.config.settings import Settings
from app.evidence.processor import load_evidence
from app.storage.incident_store import IncidentStore
from app.webapp.analysis_parser import parse_analysis
from app.webapp.graph_builder import build_incident_graph
from app.webapp.status import build_status


class ToggleableCollector(Protocol):
    @property
    def enabled(self) -> bool: ...
    def set_enabled(self, enabled: bool) -> None: ...


# Keys here are the only settings this page can toggle at runtime — deliberately
# limited to the privacy-sensitive, opt-in collectors. Core monitoring (system
# metrics, processes, OS events) isn't exposed here: turning it off would break
# the tool's actual purpose, so that stays a config.yaml-only decision.
TOGGLE_DESCRIPTIONS = {
    "screenshots": "Periodic screenshots of your screen, used as evidence when an incident happens.",
    "terminal": "Terminal commands (never output), via a shell hook you opt into separately.",
}

logger = logging.getLogger(__name__)

_SAFE_ID_RE = re.compile(r"^[A-Za-z0-9_-]+$")

_STATIC_DIR = Path(__file__).parent / "static"
_TEMPLATE_DIR = Path(__file__).parent / "templates"


def create_app(
    buffer: CircularBuffer,
    store: IncidentStore,
    settings: Settings,
    toggleable_collectors: dict[str, ToggleableCollector] | None = None,
) -> Flask:
    app = Flask(__name__, static_folder=str(_STATIC_DIR), template_folder=str(_TEMPLATE_DIR))
    toggleable_collectors = toggleable_collectors or {}

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.get("/incidents/<incident_id>")
    def incident_page(incident_id: str):
        if not _SAFE_ID_RE.match(incident_id):
            abort(404)
        return render_template("incident.html", incident_id=incident_id)

    @app.get("/settings")
    def settings_page():
        return render_template("settings.html")

    @app.get("/api/settings")
    def api_settings_get():
        return jsonify(
            {
                key: {"enabled": collector.enabled, "description": TOGGLE_DESCRIPTIONS.get(key, "")}
                for key, collector in toggleable_collectors.items()
            }
        )

    @app.post("/api/settings")
    def api_settings_post():
        body = request.get_json(silent=True) or {}
        updated = {}
        for key, value in body.items():
            collector = toggleable_collectors.get(key)
            if collector is None or not isinstance(value, bool):
                continue
            collector.set_enabled(value)
            updated[key] = collector.enabled
        return jsonify(updated)

    @app.get("/api/status")
    def api_status():
        recent = store.list_recent(limit=5)
        return jsonify(build_status(buffer, settings.triggers.system_detector, recent))

    @app.get("/api/incidents")
    def api_incidents():
        rows = store.list_recent(limit=50)
        return jsonify(
            [
                {
                    "incident_id": r["incident_id"],
                    "created_at": r["created_at"],
                    "trigger_name": r["trigger_name"],
                    "trigger_reason": r["trigger_reason"],
                    "event_count": r["event_count"],
                    "analysis_succeeded": bool(r["analysis_succeeded"]),
                }
                for r in rows
            ]
        )

    @app.get("/api/incidents/<incident_id>")
    def api_incident_detail(incident_id: str):
        if not _SAFE_ID_RE.match(incident_id):
            abort(404)
        row = store.get(incident_id)
        if row is None:
            abort(404)

        evidence = load_evidence(Path(row["output_dir"]))
        analysis_text = row["analysis_text"] or ""
        graph = build_incident_graph(evidence, analysis_text) if evidence else {"nodes": [], "edges": []}
        screenshot_url = None
        if evidence and evidence.representative_screenshot:
            screenshot_url = f"/media/{incident_id}/{Path(evidence.representative_screenshot).name}"

        return jsonify(
            {
                "incident_id": row["incident_id"],
                "created_at": row["created_at"],
                "trigger_name": row["trigger_name"],
                "trigger_reason": row["trigger_reason"],
                "event_count": row["event_count"],
                "model_used": row["model_used"],
                "analysis_succeeded": bool(row["analysis_succeeded"]),
                "analysis_text": analysis_text,
                "analysis_sections": parse_analysis(analysis_text).model_dump(),
                "correlations": [c.model_dump() for c in evidence.correlations] if evidence else [],
                "graph": graph,
                "screenshot_url": screenshot_url,
            }
        )

    @app.get("/media/<incident_id>/<filename>")
    def media(incident_id: str, filename: str):
        if not _SAFE_ID_RE.match(incident_id):
            abort(404)
        row = store.get(incident_id)
        if row is None:
            abort(404)

        screenshots_dir = (Path(row["output_dir"]) / "screenshots").resolve()
        candidate = (screenshots_dir / filename).resolve()
        if screenshots_dir not in candidate.parents or not candidate.is_file():
            abort(404)
        return send_file(candidate)

    return app


class WebServer:
    """Runs the dashboard Flask app in a background thread, bound to
    localhost only. Uses werkzeug's make_server directly (instead of
    app.run()) so stop() can shut it down cleanly like every other
    collector in this project."""

    def __init__(
        self,
        buffer: CircularBuffer,
        store: IncidentStore,
        settings: Settings,
        toggleable_collectors: dict[str, ToggleableCollector] | None = None,
    ) -> None:
        self._settings = settings
        self._app = create_app(buffer, store, settings, toggleable_collectors)
        self._server = None
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if not self._settings.web.enabled or self._thread is not None:
            return
        self._server = make_server(self._settings.web.host, self._settings.web.port, self._app)
        self._thread = threading.Thread(target=self._server.serve_forever, name="web-dashboard", daemon=True)
        self._thread.start()
        logger.info("dashboard listening on http://%s:%d", self._settings.web.host, self._settings.web.port)

    def stop(self) -> None:
        if self._server:
            self._server.shutdown()
        if self._thread:
            self._thread.join(timeout=5)
            self._thread = None
            self._server = None
