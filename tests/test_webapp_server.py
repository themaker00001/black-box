from app.buffer.circular_buffer import CircularBuffer
from app.config.settings import Settings
from app.storage.incident_store import IncidentStore
from app.webapp.server import create_app


class FakeToggleable:
    def __init__(self, enabled: bool = False) -> None:
        self._enabled = enabled

    @property
    def enabled(self) -> bool:
        return self._enabled

    def set_enabled(self, enabled: bool) -> None:
        self._enabled = enabled


def _client(tmp_path, toggleable_collectors=None):
    buf = CircularBuffer(retention_seconds=60)
    store = IncidentStore(tmp_path / "blackbox.db")
    app = create_app(buf, store, Settings(), toggleable_collectors)
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


def test_settings_page_loads(tmp_path):
    client, _ = _client(tmp_path)
    resp = client.get("/settings")
    assert resp.status_code == 200
    assert b"Settings" in resp.data


def test_api_settings_get_reports_current_state(tmp_path):
    client, _ = _client(tmp_path, {"screenshots": FakeToggleable(enabled=True), "terminal": FakeToggleable(enabled=False)})
    resp = client.get("/api/settings")
    body = resp.get_json()
    assert body["screenshots"]["enabled"] is True
    assert body["terminal"]["enabled"] is False
    assert "description" in body["screenshots"]


def test_api_settings_get_is_empty_without_collectors(tmp_path):
    client, _ = _client(tmp_path)
    resp = client.get("/api/settings")
    assert resp.get_json() == {}


def test_api_settings_post_toggles_a_collector(tmp_path):
    screenshots = FakeToggleable(enabled=False)
    client, _ = _client(tmp_path, {"screenshots": screenshots})

    resp = client.post("/api/settings", json={"screenshots": True})

    assert resp.get_json() == {"screenshots": True}
    assert screenshots.enabled is True


def test_api_settings_post_ignores_unknown_keys(tmp_path):
    screenshots = FakeToggleable(enabled=False)
    client, _ = _client(tmp_path, {"screenshots": screenshots})

    resp = client.post("/api/settings", json={"not_a_real_setting": True})

    assert resp.get_json() == {}
    assert screenshots.enabled is False


def test_api_settings_post_ignores_non_boolean_values(tmp_path):
    screenshots = FakeToggleable(enabled=False)
    client, _ = _client(tmp_path, {"screenshots": screenshots})

    resp = client.post("/api/settings", json={"screenshots": "yes please"})

    assert resp.get_json() == {}
    assert screenshots.enabled is False
