import requests

from app.config import Config
from app.services import search_provider


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.exceptions.HTTPError(f"HTTP {self.status_code}")

    def json(self):
        return self._payload


def test_null_provider_when_not_configured(monkeypatch):
    monkeypatch.setattr(Config, "SEARCH_PROVIDER", "none")
    monkeypatch.setattr(Config, "SEARCH_API_KEY", "")
    result = search_provider.search_web("anything")
    assert result["available"] is False
    assert result["results"] == []
    assert result["error"] == "search_provider_not_configured"


def test_empty_query_short_circuits():
    result = search_provider.search_web("")
    assert result["error"] == "empty_query"


def test_brave_provider_parses_results(monkeypatch):
    monkeypatch.setattr(Config, "SEARCH_API_KEY", "test-key")
    monkeypatch.setattr(Config, "SEARCH_PROVIDER", "brave")
    payload = {
        "web": {
            "results": [
                {"title": "Bummer", "url": "https://bummer.in", "description": "Innerwear"},
                {"title": "Bummer LinkedIn", "url": "https://www.linkedin.com/company/bummer", "description": ""},
            ]
        }
    }
    monkeypatch.setattr(requests, "get", lambda *a, **k: FakeResponse(payload))
    provider = search_provider.BraveProvider()
    results = provider.search("bummer")
    assert len(results) == 2
    assert results[0].url == "https://bummer.in"
    assert results[0].domain == "bummer.in"
    # LinkedIn should score higher than a generic domain.
    assert any(r.trust_score >= 3 for r in results)


def test_bing_provider_parses_results(monkeypatch):
    monkeypatch.setattr(Config, "SEARCH_API_KEY", "test-key")
    monkeypatch.setattr(Config, "SEARCH_PROVIDER", "bing")
    payload = {
        "webPages": {
            "value": [
                {"name": "Rustic Art", "url": "https://www.rusticart.in", "snippet": "Natural soaps"},
            ]
        }
    }
    monkeypatch.setattr(requests, "get", lambda *a, **k: FakeResponse(payload))
    provider = search_provider.BingProvider()
    results = provider.search("rustic art")
    assert len(results) == 1
    assert results[0].title == "Rustic Art"


def test_provider_request_failure_is_handled(app, test_db, monkeypatch):
    monkeypatch.setattr(Config, "SEARCH_API_KEY", "test-key")
    monkeypatch.setattr(Config, "SEARCH_PROVIDER", "brave")

    def boom(*args, **kwargs):
        raise requests.exceptions.ConnectionError("network down")

    monkeypatch.setattr(requests, "get", boom)
    with app.app_context():
        result = search_provider.search_web("bummer", use_cache=False)
    assert result["available"] is True
    assert result["results"] == []
    assert result["error"] == "provider_request_failed"


def test_provider_bad_payload_is_handled(app, test_db, monkeypatch):
    monkeypatch.setattr(Config, "SEARCH_API_KEY", "test-key")
    monkeypatch.setattr(Config, "SEARCH_PROVIDER", "brave")
    monkeypatch.setattr(requests, "get", lambda *a, **k: FakeResponse({"nope": True}))
    with app.app_context():
        result = search_provider.search_web("bummer", use_cache=False)
    # Brave parser tolerates a missing "web" key and returns zero results.
    assert result["available"] is True
    assert result["results"] == []
