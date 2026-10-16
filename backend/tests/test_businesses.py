def test_get_business_by_slug(client, seeded):
    response = client.get("/api/businesses/gulabo-jaipur")
    assert response.status_code == 200
    data = response.get_json()
    assert data["company_name"] == "Gulabo Jaipur"
    assert data["business_email"] == "sales@gulabojaipur.com"
    assert "verification_summary" in data


def test_direct_profile_access_without_homepage(client, seeded):
    # Simulates a recipient opening a shared link directly.
    response = client.get("/api/businesses/bunaai")
    assert response.status_code == 200
    assert response.get_json()["slug"] == "bunaai"


def test_missing_business_returns_404(client, seeded):
    assert client.get("/api/businesses/does-not-exist").status_code == 404


def test_invalid_identifier_rejected(client, seeded):
    assert client.get("/api/businesses/..%2F..%2Fetc").status_code in (400, 404, 422)
    assert client.get("/api/businesses/bad$slug").status_code == 422


def test_missing_contact_fields_are_null_not_invented(client, seeded):
    data = client.get("/api/businesses/bunaai").get_json()
    # The sample "Bunaai" row has no phone; it must be null, never guessed.
    assert data["business_phone"] in (None, "")
    assert data["business_email"] in (None, "")


def test_refresh_reports_provider_unavailable(client, seeded):
    response = client.post("/api/businesses/gulabo-jaipur/refresh")
    assert response.status_code == 200
    body = response.get_json()
    assert body["found"] is True
    assert body["provider_available"] is False


def test_refresh_uses_provider_when_available(client, seeded, monkeypatch):
    fake = {
        "provider": "brave",
        "available": True,
        "error": None,
        "results": [
            {
                "title": "Bunaai official",
                "url": "https://www.bunai.com",
                "snippet": "",
                "domain": "bunai.com",
                "source": "brave",
                "trust_score": 4,
            }
        ],
    }
    monkeypatch.setattr("app.services.search_provider.search_web", lambda *a, **k: fake)
    response = client.post("/api/businesses/bunaai/refresh")
    assert response.status_code == 200
    assert response.get_json()["provider_available"] is True
