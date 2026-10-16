import json


def test_exact_search(client, seeded):
    response = client.get("/api/search?q=Gulabo Jaipur")
    assert response.status_code == 200
    data = response.get_json()
    assert data["results"]
    assert data["results"][0]["company_name"] == "Gulabo Jaipur"


def test_search_is_case_insensitive(client, seeded):
    data = client.get("/api/search?q=gulabo jaipur").get_json()
    names = [r["company_name"] for r in data["results"]]
    assert "Gulabo Jaipur" in names


def test_partial_search_matches(client, seeded):
    data = client.get("/api/search?q=gulab").get_json()
    assert any(r["company_name"] == "Gulabo Jaipur" for r in data["results"])


def test_search_matches_alternate_name(client, seeded):
    # "Bunai" is an alias of "Bunaai".
    data = client.get("/api/search?q=Bunai").get_json()
    assert any(r["company_name"] == "Bunaai" for r in data["results"])


def test_search_requires_query_or_filter(client, seeded):
    response = client.get("/api/search")
    assert response.status_code == 422


def test_browse_by_city_without_query(client, seeded):
    data = client.get("/api/search?city=Jaipur").get_json()
    assert data["total"] >= 2


def test_browse_by_category_without_query(client, seeded):
    data = client.get("/api/search?category=Fashion D2C Brand").get_json()
    assert data["total"] >= 1


def test_not_found_company_reports_web_unavailable(client, seeded):
    data = client.get("/api/search?q=HelmetShopee").get_json()
    assert data["results"] == []
    assert data["web_search"]["available"] is False
    assert data["web_search"]["error"] == "search_provider_not_configured"


def test_web_search_candidate_is_added_when_provider_returns_results(
    client, seeded, monkeypatch
):
    fake = {
        "provider": "brave",
        "available": True,
        "error": None,
        "cached": False,
        "results": [
            {
                "title": "HelmetShopee - Official",
                "url": "https://helmetshopee.in/contact",
                "snippet": "Reach us at support@helmetshopee.in",
                "domain": "helmetshopee.in",
                "source": "brave",
                "trust_score": 5,
            }
        ],
    }
    monkeypatch.setattr(
        "app.services.search_provider.search_web", lambda *a, **k: fake
    )
    data = client.get("/api/search?q=HelmetShopee").get_json()
    assert data["source"] == "web"
    candidate = data["web_candidates"][0]
    assert candidate["company_name"] == "HelmetShopee"
    assert candidate["data_origin"] == "web_search"
    # The only email surfaced is the one present in the snippet, never guessed.
    assert candidate["business_email"] == "support@helmetshopee.in"
    assert candidate["source_urls"] == ["https://helmetshopee.in/contact"]


def test_search_respects_limit(client, seeded):
    data = client.get("/api/search?city=Jaipur&limit=1").get_json()
    assert len(data["results"]) == 1
    assert data["total"] == 2


def test_post_search_validates_body(client, seeded):
    response = client.post("/api/search", json={})
    assert response.status_code == 422


def test_post_search_success(client, seeded):
    response = client.post("/api/search", json={"query": "Bunaai"})
    assert response.status_code == 200
    assert response.get_json()["results"]
