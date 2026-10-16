from app import db as db_module
from app.db import DatabaseUnavailable


def test_health_reports_ok(client, seeded):
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "ok"
    assert data["database"]["connected"] is True


def test_health_reports_degraded_when_db_down(client, monkeypatch):
    monkeypatch.setattr(db_module, "ping", lambda: (False, "ServerSelectionTimeoutError"))
    response = client.get("/api/health")
    assert response.status_code == 503
    assert response.get_json()["status"] == "degraded"


def test_search_returns_503_when_db_unavailable(client, monkeypatch):
    def unavailable():
        raise DatabaseUnavailable("Database is not reachable")

    monkeypatch.setattr(db_module, "get_db", unavailable)
    response = client.get("/api/search?q=bummer")
    assert response.status_code == 503
    assert response.get_json()["error"]["code"] == "service_unavailable"


def test_business_returns_503_when_db_unavailable(client, monkeypatch):
    def unavailable():
        raise DatabaseUnavailable("Database is not reachable")

    monkeypatch.setattr(db_module, "get_db", unavailable)
    response = client.get("/api/businesses/bummer")
    assert response.status_code == 503


def test_unknown_route_returns_json_404(client):
    response = client.get("/api/does-not-exist")
    assert response.status_code == 404
    assert response.is_json
