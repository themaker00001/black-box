from app.buffer.circular_buffer import CircularBuffer
from app.config.settings import Settings
from app.storage.incident_store import IncidentStore
from app.webapp.server import create_app


def _client(tmp_path):
    buf = CircularBuffer(retention_seconds=60)
    store = IncidentStore(tmp_path / "blackbox.db")
    app = create_app(buf, store, Settings())
    return app.test_client(), store


def test_index_page_loads(tmp_path):
    client, _ = _client(tmp_path)
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"Black Box" in resp.data


def test_api_status_returns_json(tmp_path):
    client, _ = _client(tmp_path)
    resp = client.get("/api/status")
    assert resp.status_code == 200
    assert "ok" in resp.get_json()


def test_api_incidents_empty_list(tmp_path):
    client, _ = _client(tmp_path)
    resp = client.get("/api/incidents")
    assert resp.status_code == 200
    assert resp.get_json() == []


def test_unknown_incident_returns_404(tmp_path):
    client, _ = _client(tmp_path)
    resp = client.get("/api/incidents/does-not-exist")
    assert resp.status_code == 404


def test_incident_id_path_traversal_is_rejected(tmp_path):
    client, _ = _client(tmp_path)
    resp = client.get("/media/..%2F..%2Fetc/passwd")
    assert resp.status_code == 404
