"""Research pipeline tests with mocked external services."""
from __future__ import annotations

import uuid

import pytest

from app.services import company_research_service as crs
from app.services import extraction, page_fetcher, search_provider


def _unique(prefix: str) -> str:
    return f"{prefix} {uuid.uuid4().hex[:8]}"


def _fake_web(payload=None):
    if payload is None:
        payload = {
            "provider": "brave",
            "available": True,
            "error": None,
            "cached": False,
            "results": [
                {
                    "title": "Bummer - Official Site",
                    "url": "https://bummer.in",
                    "snippet": "Bummer is a D2C loungewear brand. Founder: Lakshmi Lalwani. contact@bummer.in",
                    "source": "brave",
                    "domain": "bummer.in",
                    "trust_score": 3,
                },
                {
                    "title": "Bummer LinkedIn",
                    "url": "https://www.linkedin.com/company/bummer",
                    "snippet": "Bummer · Founder Lakshmi Lalwani · +91 9876543210",
                    "source": "brave",
                    "domain": "linkedin.com",
                    "trust_score": 3,
                },
            ],
        }
    return payload


def _fake_pages():
    return [
        {
            "url": "https://bummer.in",
            "ok": True,
            "title": "Bummer",
            "text": (
                "Bummer - premium loungewear.\n"
                "Founder: Lakshmi Lalwani\n"
                "Email: contact@bummer.in\n"
                "Phone: +91 9876543210\n"
                "Address: 12 MG Road Bengaluru Karnataka"
            ),
            "error": None,
        }
    ]


@pytest.fixture(autouse=True)
def _clean_research_state(app):
    """Wipe research collections before every test for isolation."""
    with app.app_context():
        from app import db as db_module

        database = db_module.get_client()["seller_finder_test"]
        for name in ("companies", "research_jobs", "source_evidence", "saved_leads"):
            database[name].delete_many({})
    yield


def test_start_research():
    job = crs.start_research(_unique("HelmetShopee"))
    assert job["job_id"]
    assert job["status"] == "running"


def test_get_research():
    name = _unique("Acme")
    job = crs.start_research(name)
    got = crs.get_research(job["job_id"])
    assert got is not None
    assert got["company_name"] == name


def test_research_completed_with_mocked_search(monkeypatch):
    monkeypatch.setattr(crs.Config, "RESEARCH_ASYNC", False, raising=False)
    monkeypatch.setattr(search_provider, "search_web", lambda q, **k: _fake_web())
    monkeypatch.setattr(crs.page_fetcher, "fetch_pages", lambda urls, **k: _fake_pages())
    monkeypatch.setattr(extraction, "_ollama_available", lambda: False)

    name = _unique("Bummer Labs")
    results = crs.research_company(name)
    assert results["company_name"] == name
    assert results["contacts"]["business_email"] == "contact@bummer.in"
    assert results["founders"], "founder should be extracted from evidence"
    assert results["founders"][0]["name"]
    assert any(e.get("value") for e in results["field_evidence"])
    assert results["from_cache"] is False
    assert results["company_id"]


def test_research_cache_hit_skips_external_search(monkeypatch):
    monkeypatch.setattr(crs.Config, "RESEARCH_ASYNC", False, raising=False)

    calls = {"search": 0}

    def counting_search(q, **k):
        calls["search"] += 1
        return _fake_web()

    monkeypatch.setattr(search_provider, "search_web", counting_search)
    monkeypatch.setattr(crs.page_fetcher, "fetch_pages", lambda urls, **k: _fake_pages())
    monkeypatch.setattr(extraction, "_ollama_available", lambda: False)

    name = _unique("CacheDemo Co")
    first = crs.research_company(name)
    assert calls["search"] == 1
    assert first["from_cache"] is False

    job2 = crs.start_research(name)
    assert job2["status"] == "completed"
    assert job2["from_cache"] is True
    assert calls["search"] == 1  # no extra external call
    assert job2["results"]["contacts"]["business_email"] == "contact@bummer.in"


def test_duplicate_concurrent_jobs_reused(monkeypatch):
    monkeypatch.setattr(crs.Config, "RESEARCH_ASYNC", False, raising=False)
    name = _unique("DupCoXYZ")
    job1 = crs.start_research(name)
    job2 = crs.start_research(name)
    assert job1["job_id"] == job2["job_id"]


def test_provider_not_configured_is_honest(monkeypatch):
    monkeypatch.setattr(crs.Config, "RESEARCH_ASYNC", False, raising=False)
    monkeypatch.setattr(
        search_provider,
        "search_web",
        lambda q, **k: {
            "provider": "none",
            "available": False,
            "results": [],
            "error": "search_provider_not_configured",
        },
    )
    results = crs.research_company(_unique("UnknownNoProvider Ltd"))
    assert results["founders"] == []
    assert results["contacts"] == {}
    assert results.get("search_error") == "search_provider_not_configured"
    message = (results.get("message") or "").lower()
    assert "search provider" in message or "configured" in message


def test_missing_founder_fields_are_empty_not_invented(monkeypatch):
    monkeypatch.setattr(crs.Config, "RESEARCH_ASYNC", False, raising=False)
    bare = {
        "provider": "brave",
        "available": True,
        "error": None,
        "cached": False,
        "results": [
            {
                "title": "NoFounder Corp",
                "url": "https://nofounder.example.com",
                "snippet": "A generic company page with no people mentioned.",
                "source": "brave",
                "domain": "nofounder.example.com",
                "trust_score": 1,
            }
        ],
    }
    monkeypatch.setattr(search_provider, "search_web", lambda q, **k: bare)
    monkeypatch.setattr(
        crs.page_fetcher,
        "fetch_pages",
        lambda urls, **k: [
            {
                "url": "https://nofounder.example.com",
                "ok": True,
                "title": "NoFounder",
                "text": "We make things. Contact us via the form.",
                "error": None,
            }
        ],
    )
    monkeypatch.setattr(extraction, "_ollama_available", lambda: False)

    results = crs.research_company(_unique("NoFounder Corp"))
    founder_names = [f.get("name") for f in results.get("founders", [])]
    assert all(not n for n in founder_names) or results["founders"] == []
    email = results["contacts"].get("business_email", "")
    assert email in ("", None) or "@" in email


def test_refresh_reruns_pipeline(monkeypatch):
    monkeypatch.setattr(crs.Config, "RESEARCH_ASYNC", False, raising=False)
    monkeypatch.setattr(search_provider, "search_web", lambda q, **k: _fake_web())
    monkeypatch.setattr(crs.page_fetcher, "fetch_pages", lambda urls, **k: _fake_pages())
    monkeypatch.setattr(extraction, "_ollama_available", lambda: False)

    name = _unique("RefreshCo")
    job = crs.start_research(name, force=True)
    crs.research_company(name, job_id=job["job_id"])
    refreshed = crs.refresh_research(job["job_id"])
    assert refreshed["status"] == "completed"
    assert refreshed["from_cache"] is False


def test_start_research_rejects_empty():
    with pytest.raises(ValueError):
        crs.start_research("   ")


def test_extraction_never_returns_values_absent_from_evidence():
    payload = {
        "company_name": "Ghost Co",
        "search_results": [
            {"title": "Ghost", "url": "https://ghost.example", "snippet": "Nothing personal here."}
        ],
        "pages": [
            {"url": "https://ghost.example", "ok": True, "title": "Ghost", "text": "We sell widgets."}
        ],
        "source_urls": ["https://ghost.example"],
        "evidence_snippets": [],
    }
    out = extraction.extract_structured(payload)
    assert out["business_email"] in ("", None)
    assert out["business_phone"] in ("", None)
    assert out["founder_name"] in ("", None)
    assert out["extraction_method"] in ("deterministic", "ollama")


def test_page_fetcher_rejects_private_urls():
    for bad in (
        "http://localhost:5000",
        "http://127.0.0.1",
        "http://169.254.169.254/latest/meta-data",
        "file:///etc/passwd",
        "javascript:alert(1)",
    ):
        page = page_fetcher.fetch_page(bad)
        assert page["ok"] is False


def test_page_fetcher_html_to_text():
    text = page_fetcher.html_to_text(
        "<html><script>x()</script><h1>Hi</h1><p>Body &amp; more</p></html>"
    )
    assert "Hi" in text
    assert "Body & more" in text
    assert "x()" not in text


def test_research_job_listed():
    name = _unique("ListMe Inc")
    job = crs.start_research(name)
    jobs = crs.list_research(limit=50)
    assert any(j["job_id"] == job["job_id"] for j in jobs)


def test_research_api_start_and_poll(client, monkeypatch):
    monkeypatch.setattr(crs.Config, "RESEARCH_ASYNC", False, raising=False)
    monkeypatch.setattr(search_provider, "search_web", lambda q, **k: _fake_web())
    monkeypatch.setattr(crs.page_fetcher, "fetch_pages", lambda urls, **k: _fake_pages())
    monkeypatch.setattr(extraction, "_ollama_available", lambda: False)

    login = client.post(
        "/api/auth/login",
        json={"email": "admin@gmail.com", "password": "Test@123"},
    )
    assert login.status_code == 200
    token = login.get_json()["token"]

    resp = client.post(
        "/api/research",
        json={"company_name": _unique("ApiResearch Co")},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code in (200, 202)
    job = resp.get_json()
    assert job["job_id"]

    poll = client.get(
        f"/api/research/{job['job_id']}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert poll.status_code == 200
    body = poll.get_json()
    assert body["status"] in ("running", "completed")
    if body["status"] == "completed":
        assert body["results"] is not None


def test_research_requires_auth(client, monkeypatch):
    monkeypatch.setitem(client.application.config, "AUTH_REQUIRED", True)
    resp = client.post("/api/research", json={"company_name": "X"})
    assert resp.status_code == 401


def test_research_validation(client, auth_headers):
    resp = client.post("/api/research", json={}, headers=auth_headers)
    assert resp.status_code == 422


def test_research_not_found(client, auth_headers):
    resp = client.get("/api/research/no-such-job-id", headers=auth_headers)
    assert resp.status_code == 404
